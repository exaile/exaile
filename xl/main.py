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

# Here's where it all begins.....
#
# Holds the main Exaile class, whose instantiation starts up the entiriety
# of Exaile and which also handles Exaile shutdown.
#
# Also takes care of parsing commandline options.

import os
import platform
import sys
import threading

from xl import logger_setup
from xl.nls import gettext as _

# Imported later to avoid PyGObject imports just for --help.
Gio = common = xdg = None

def _do_heavy_imports():
    global Gio, common, xdg

    from gi.repository import Gio
    from xl import common, xdg

# placeholder, - xl.version can be slow to import, which would slow down
# cli args. Thus we import __version__ later.
__version__ = None

logger = None

class Exaile(object):
    _exaile = None

    def __get_player(self):
        raise DeprecationWarning('Using exaile.player is deprecated: '
                                 'import xl.player.PLAYER instead.')

    def __get_queue(self):
        raise DeprecationWarning('Using exaile.queue is deprecated: '
                                 'import xl.player.QUEUE instead.')

    def __get_lyrics(self):
        raise DeprecationWarning('Using exaile.lyrics is deprecated: '
                                 'import xl.lyrics.MANAGER instead.')

    player = property(__get_player)
    queue = property(__get_queue)
    lyrics = property(__get_lyrics)

    def __init__(self):
        """
            Initializes Exaile.
        """
        self.quitting = False
        self.loading = True

        # NOTE: This automatically exits on --help.
        try:
            (self.options, self.args) = self.get_options().parse_args()
        except UnicodeDecodeError:
            (self.options, self.args) = self.get_options(unicode_bug_happened=True).parse_args()

        if self.options.ShowVersion:
            self.version()
            return

        _do_heavy_imports()

        if self.options.UseDataDir:
            xdg.data_dirs.insert(1, self.options.UseDataDir)

        # this is useful on Win32, because you cannot set these directories
        # via environment variables
        if self.options.UseAllDataDir:
            xdg.data_home = self.options.UseAllDataDir
            xdg.data_dirs.insert(0, xdg.data_home)
            xdg.config_home = self.options.UseAllDataDir
            xdg.config_dirs.insert(0, xdg.config_home)
            xdg.cache_home = self.options.UseAllDataDir
            
        try:
            xdg._make_missing_dirs()
        except OSError, e:
            print >> sys.stderr, 'ERROR: Could not create configuration directories: %s' % str(e)
            return
            

        # Make event debug imply debug
        if self.options.DebugEvent:
            self.options.Debug = True

        try:
            logger_setup.start_logging(self.options.Debug,
                                       self.options.Quiet,
                                       self.options.DebugThreads,
                                       self.options.ModuleFilter,
                                       self.options.LevelFilter)
        except OSError, e:
            print >> sys.stderr, 'ERROR: could not setup logging: %s' % str(e)
            return
        
        global logger
        import logging
        logger = logging.getLogger(__name__)

        # Late import ensures xl.event uses correct logger
        from xl import event

        if self.options.EventFilter:
            event.EVENT_MANAGER.logger_filter = self.options.EventFilter
            self.options.DebugEvent = True

        if self.options.DebugEvent:
            event.EVENT_MANAGER.use_logger = True
            self.options.Debug = True

        # initial mainloop setup. The actual loop is started later,
        # if necessary
        self.mainloop_init()

        #initialize DbusManager
        if self.options.StartGui and self.options.Dbus:
            from xl import xldbus
            exit = xldbus.check_exit(self.options, self.args)
            if exit == "exit":
                sys.exit(0)
            elif exit == "command":
                if not self.options.StartAnyway:
                    sys.exit(0)
            self.dbus = xldbus.DbusManager(self)

        # import version, see note above
        global __version__
        from xl.version import __version__

        #load the rest.
        self.__init()

        #handle delayed commands
        if self.options.StartGui and self.options.Dbus and \
                self.options.StartAnyway and exit == "command":
            xldbus.run_commands(self.options, self.dbus)

        #connect dbus signals
        if self.options.StartGui and self.options.Dbus:
            self.dbus._connect_signals()

        # On SIGTERM, quit normally.
        import signal
        signal.signal(signal.SIGTERM, (lambda sig, stack: self.quit()))

        # run the GUIs mainloop, if needed
        if self.options.StartGui:
            import xlgui
            xlgui.mainloop()

    def __init(self):
        """
            Initializes Exaile
        """
        # pylint: disable-msg=W0201
        logger.info("Loading Exaile %s on Python %s..." % (__version__, platform.python_version()))

        logger.info("Loading settings...")
        try:
            from xl import settings
        except common.VersionError:
            common.log_exception(log=logger)
            sys.exit(1)
            
        logger.debug("Settings loaded from %s" % settings.location)
        
        # display locale information if available
        try:
            import locale
            lc, enc = locale.getlocale()
            if enc is not None:
                logger.info("Using %s %s locale" % (lc, enc))
            else:
                logger.info("Using unknown locale")
        except:
            pass

        splash = None

        if self.options.StartGui:
            from xl import settings

            if settings.get_option('gui/use_splash', True):
                from xlgui.widgets.info import Splash

                splash = Splash()
                splash.show()

        firstrun = settings.get_option("general/first_run", True)

        if not self.options.NoImport and \
                (firstrun or self.options.ForceImport):
            try:
                sys.path.insert(0, xdg.get_data_path("migrations"))
                import migration_200907100931 as migrator
                del sys.path[0]
                migrator.migrate(force=self.options.ForceImport)
                del migrator
            except:
                common.log_exception(log=logger,
                        message=_("Failed to migrate from 0.2.14"))

        # Migrate old rating options
        from xl.migrations.settings import rating
        rating.migrate()

        # Migrate builtin OSD to plugin
        from xl.migrations.settings import osd
        osd.migrate()

        # Initialize plugin manager
        from xl import plugins
        self.plugins = plugins.PluginsManager(self)
        
        if not self.options.SafeMode:
            logger.info("Loading plugins...")
            self.plugins.load_enabled()
        else:
            logger.info("Safe mode enabled, not loading plugins.")

        # Initialize the collection
        logger.info("Loading collection...")
        from xl import collection
        try:
            self.collection = collection.Collection("Collection",
                    location=os.path.join(xdg.get_data_dir(), 'music.db'))
        except common.VersionError:
            common.log_exception(log=logger)
            sys.exit(1)

        from xl import event
        # Set up the player and playback queue
        from xl import player
        event.log_event("player_loaded", player.PLAYER, None)

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
        dynamic.MANAGER.collection = self.collection

        # Initalize device manager
        logger.info("Loading devices...")
        from xl import devices
        self.devices = devices.DeviceManager()
        event.log_event("device_manager_ready", self, None)

        # Initialize dynamic device discovery interface
        # -> if initialized and connected, then the object is not None
        
        self.udisks2 = None
        self.udisks = None
        self.hal = None
        
        if self.options.Hal:
            from xl import hal
                
            udisks2 = hal.UDisks2(self.devices)
            if udisks2.connect():
                self.udisks2 = udisks2
            else:
                udisks = hal.UDisks(self.devices)
                if udisks.connect():
                    self.udisks = udisks
                else:
                    self.hal = hal.HAL(self.devices)
                    self.hal.connect()
        else:
            self.hal = None

        # Radio Manager
        from xl import radio
        self.stations = playlist.PlaylistManager('radio_stations')
        self.radio = radio.RadioManager()

        self.gui = None
        # Setup GUI
        if self.options.StartGui:
            logger.info("Loading interface...")

            import xlgui
            self.gui = xlgui.Main(self)
            self.gui.main.window.show_all()
            event.log_event("gui_loaded", self, None)

            if splash is not None:
                splash.destroy()

        restore = True

        if self.gui:
            # Find out if the user just passed in a list of songs
            # TODO: find a better place to put this
            # using arg[2:] because arg[1:] will include --startgui
            
            args = [ Gio.File.new_for_path(arg).get_uri() for arg in self.args ]
            if len(args) > 0:
                restore = False
                self.gui.open_uri(args[0], play=True)
            for arg in args[1:]:
                self.gui.open_uri(arg)
            
            # kick off autoscan of libraries
            # -> don't do it in command line mode, since that isn't expected
            self.gui.rescan_collection_with_progress(True)

        if restore:
            player.QUEUE._restore_player_state(
                    os.path.join(xdg.get_data_dir(), 'player.state'))

        if firstrun:
            settings.set_option("general/first_run", False)

        self.loading = False
        Exaile._exaile = self
        event.log_event("exaile_loaded", self, None)
        # pylint: enable-msg=W0201

    def __show_splash(self):
        """
            Displays the splash screen
        """
        from xl import settings

        if not settings.get_option('gui/use_splash', True):
            return

        from xlgui.widgets.info import Splash

        splash = Splash()
        splash.show()

    def get_options(self, unicode_bug_happened=False):
        """
            Get the options for exaile
        """
        from optparse import OptionParser, OptionGroup, IndentedHelpFormatter

        if unicode_bug_happened:
            
            #
            # Bug: https://bugs.launchpad.net/exaile/+bug/1154420
            #
            # For some locales, python doesn't merge the options and
            # the headings and our translated text correctly. Unfortunately,
            # there doesn't seem to be a good way to deal with the problem
            # on Python 2.x . If we disable the usage/heading, at least
            # the options will display, despite filling all the text as ???. 
            #
            
            print >> sys.stderr, "exaile: Warning: Unicode error displaying --help, check locale settings"
            
            class OverrideHelpFormatter(IndentedHelpFormatter):
                def format_usage(self, usage):
                    return ''
                def format_heading(self, heading):
                    return ''
        else:
            class OverrideHelpFormatter(IndentedHelpFormatter):
                """
                    Merely for translation purposes
                """
                def format_usage(self, usage):
                    return '%s\n' % usage
        
        usage = _("Usage: exaile [OPTION]... [URI]")
        optionlabel = _('Options') # Merely for translation purposes
        p = OptionParser(usage=usage, add_help_option=False,
            formatter=OverrideHelpFormatter())

        group = OptionGroup(p, _('Playback Options'))
        group.add_option("-n", "--next", dest="Next", action="store_true",
                default=False, help=_("Play the next track"))
        group.add_option("-p", "--prev", dest="Prev", action="store_true",
                default=False,   help=_("Play the previous track"))
        group.add_option("-s", "--stop", dest="Stop", action="store_true",
                default=False, help=_("Stop playback"))
        group.add_option("-a", "--play", dest="Play", action="store_true",
                default=False, help=_("Play"))
        group.add_option("-u", "--pause", dest="Pause", action="store_true",
                default=False, help=_("Pause"))
        group.add_option("-t", "--play-pause", dest="PlayPause",
                action="store_true", default=False,
                help=_("Pause or resume playback"))
        group.add_option("--stop-after-current", dest="StopAfterCurrent",
                action="store_true", default=False,
                help=_("Stop playback after current track"))
        p.add_option_group(group)

        group = OptionGroup(p, _('Collection Options'))
        group.add_option("--add", dest="Add", action="store",
                # TRANSLATORS: Meta variable for --add and --export-playlist
                metavar=_("LOCATION"), help=_("Add tracks from LOCATION "
                                              "to the collection"))
        p.add_option_group(group)

        group = OptionGroup(p, _('Playlist Options'))
        group.add_option("--export-playlist", dest="ExportPlaylist",
                         # TRANSLATORS: Meta variable for --add and --export-playlist
                         action="store", metavar=_("LOCATION"),
                         help=_('Exports the current playlist to LOCATION'))
        p.add_option_group(group)

        group = OptionGroup(p, _('Track Options'))
        group.add_option("-q", "--query", dest="Query", action="store_true",
                default=False, help=_("Query player"))
        group.add_option("--format-query", dest="FormatQuery",
                         # TRANSLATORS: Meta variable for --format-query
                         action="store", metavar=_('FORMAT'),
                         help=_('Retrieves the current playback state and track information as FORMAT'))
        group.add_option("--format-query-tags", dest="FormatQueryTags",
                         # TRANSLATORS: Meta variable for --format-query-tags
                         action="store", metavar=_('TAGS'),
                         help=_('TAGS to retrieve from the current track, use with --format-query'))
        group.add_option("--gui-query", dest="GuiQuery",
                action="store_true", default=False,
                help=_("Show a popup with data of the current track"))
        group.add_option("--get-title", dest="GetTitle", action="store_true",
                default=False, help=_("Print the title of current track"))
        group.add_option("--get-album", dest="GetAlbum", action="store_true",
                default=False, help=_("Print the album of current track"))
        group.add_option("--get-artist", dest="GetArtist", action="store_true",
                default=False, help=_("Print the artist of current track"))
        group.add_option("--get-length", dest="GetLength", action="store_true",
                default=False, help=_("Print the length of current track"))
        group.add_option('--set-rating', dest="SetRating",
                # TRANSLATORS: Variable for command line options with arguments
                action='store', type='int', metavar=_('N'),
                help=_('Set rating for current track to N%'))
        group.add_option('--get-rating', dest='GetRating', action='store_true',
                default=False, help=_('Get rating for current track'))
        group.add_option("--current-position", dest="CurrentPosition",
                action="store_true", default=False,
                help=_("Print the current playback position as time"))
        group.add_option("--current-progress", dest="CurrentProgress",
                action="store_true", default=False, help=_("Print the "
                "current playback progress as percentage"))
        p.add_option_group(group)

        group = OptionGroup(p, _('Volume Options'))
        group.add_option("-i", "--increase-vol", dest="IncreaseVolume",
                # TRANSLATORS: Variable for command line options with arguments
                action="store", type="int", metavar=_("N"),
                help=_("Increases the volume by N%"))
        group.add_option("-l", "--decrease-vol", dest="DecreaseVolume",
                # TRANSLATORS: Variable for command line options with arguments
                action="store", type="int", metavar=_("N"),
                # TRANSLATORS: Meta variable for --increase-vol and--decrease-vol
                help=_("Decreases the volume by N%"))
        group.add_option("-m", "--toggle-mute", dest="ToggleMute",
                action="store_true", default=False,
                help=_("Mutes or unmutes the volume"))
        group.add_option("--get-volume", dest="GetVolume", action="store_true",
                default=False, help=_("Print the current volume percentage"))
        p.add_option_group(group)

        group = OptionGroup(p, _('Other Options'))
        group.add_option("--new", dest="NewInstance", action="store_true",
                default=False, help=_("Start new instance"))
        group.add_option("-h", "--help", action="help",
                help=_("Show this help message and exit"))
        group.add_option("--version", dest="ShowVersion", action="store_true",
                help=_("Show program's version number and exit."))
        group.add_option("--start-minimized", dest="StartMinimized",
                action="store_true", default=False,
                help=_("Start minimized (to tray, if possible)"))
        group.add_option("--toggle-visible", dest="GuiToggleVisible",
                action="store_true", default=False,
                help=_("Toggle visibility of the GUI (if possible)"))
        group.add_option("--safemode", dest="SafeMode", action="store_true",
                default=False, help=_("Start in safe mode - sometimes "
                "useful when you're running into problems"))
        group.add_option("--force-import", dest="ForceImport",
                action="store_true", default=False, help=_("Force import of"
                " old data from version 0.2.x (Overwrites current data)"))
        group.add_option("--no-import", dest="NoImport",
                action="store_true", default=False, help=_("Do not import "
                "old data from version 0.2.x"))
        group.add_option("--start-anyway", dest="StartAnyway",
                action="store_true", default=False, help=_("Make control "
                "options like --play start Exaile if it is not running"))
        p.add_option_group(group)

        group = OptionGroup(p, _('Development/Debug Options'))
        group.add_option("--datadir", dest="UseDataDir",
                metavar=_('DIRECTORY'), help=_("Set data directory"))
        group.add_option("--all-data-dir", dest="UseAllDataDir",
                metavar=_('DIRECTORY'), help=_("Set data and config directory"))
        group.add_option("--modulefilter", dest="ModuleFilter",
                action="store", type="string", metavar=_('MODULE'),
                help=_('Limit log output to MODULE'))
        group.add_option("--levelfilter", dest="LevelFilter",
                action="store", metavar=_('LEVEL'),
                help=_('Limit log output to LEVEL'),
                choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
        group.add_option("--debug", dest="Debug", action="store_true",
                default=False, help=_("Show debugging output"))
        group.add_option("--eventdebug", dest="DebugEvent",
                action="store_true", default=False, help=_("Enable debugging"
                " of xl.event. Generates LOTS of output"))
        group.add_option("--threaddebug", dest="DebugThreads",
                action="store_true", default=False, help=_("Add thread name"
                " to logging messages."))
        group.add_option("--eventfilter", dest="EventFilter",
                action='store', type='string', metavar=_('TYPE'),
                help=_("Limit xl.event debug to output of TYPE"))
        group.add_option("--quiet", dest="Quiet", action="store_true",
                default=False, help=_("Reduce level of output"))
        group.add_option('--startgui', dest='StartGui', action='store_true',
                default=False)
        group.add_option('--no-dbus', dest='Dbus', action='store_false',
                default=True, help=_("Disable D-Bus support"))
        group.add_option('--no-hal', dest='Hal', action='store_false',
                default=True, help=_("Disable HAL support."))
        p.add_option_group(group)

        return p

    def version(self):
        from xl.version import __version__
        print "Exaile", __version__
        sys.exit(0)

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
        from gi.repository import GObject

        GObject.threads_init()

        if self.options.Dbus:
            import dbus, dbus.mainloop.glib
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            dbus.mainloop.glib.threads_init()
            dbus.mainloop.glib.gthreads_init()

        if not self.options.StartGui:
            from gi.repository import GLib
            loop = GLib.MainLoop()
            context = loop.get_context()
            t = threading.Thread(target=self.__mainloop, args=(context,))
            t.daemon = True
            t.start()

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
    
    def get_user_agent_string(self, plugin_name=None):
        '''
            Returns an approrpiately formatted User-agent string for 
            web requests. When possible, plugins should use this to
            format user agent strings.
            
            Users can control this agent string by manually setting
            general/user_agent and general/user_agent_w_plugin in settings.ini
            
            :param plugin_name: the name of the plugin
        '''
        
        version = __version__
        if '+' in version:  # strip out revision identifier
            version = version[:version.index('+')]
        
        fmt = {
            'version': version
        }
        
        if not hasattr(self, '_user_agent_no_plugin'):
                    
            from xl import settings
            
            default_no_plugin = 'Exaile/%(version)s (+http://www.exaile.org)'
            default_plugin = 'Exaile/%(version)s %(plugin_name)s/%(plugin_version)s (+http://www.exaile.org)'
        
            self._user_agent_no_plugin = \
                settings.get_option('general/user_agent', default_no_plugin)
            self._user_agent_w_plugin = \
                settings.get_option('general/user_agent_w_plugin', default_plugin)
        
        if plugin_name is not None:
            plugin_info = self.plugins.get_plugin_info(plugin_name)
            
            fmt['plugin_name'] = plugin_info['Name'].replace(' ', '')
            fmt['plugin_version'] = plugin_info['Version']
            
            return self._user_agent_w_plugin % fmt
        else:
            return self._user_agent_no_plugin % fmt

    def quit(self, restart=False):
        """
            Exits Exaile normally. Takes care of saving
            preferences, databases, etc.

            :param restart: Whether to directly restart
            :type restart: bool
        """
        if self.quitting:
            return
        self.quitting = True
        logger.info("Exaile is shutting down...")

        logger.info("Disabling plugins...")
        for k, plugin in self.plugins.enabled_plugins.iteritems():
            if hasattr(plugin, 'teardown'):
                try:
                    plugin.teardown(self)
                except:
                    pass

        from xl import event
        # this event should be used by modules that dont need
        # to be saved in any particular order. modules that might be
        # touched by events triggered here should be added statically
        # below.
        event.log_event("quit_application", self, None)

        logger.info("Saving state...")
        self.plugins.save_enabled()

        if self.gui:
            self.gui.quit()

        from xl import covers
        covers.MANAGER.save()

        self.collection.save_to_location()

        # Save order of custom playlists
        self.playlists.save_order()
        self.stations.save_order()

        # save player, queue
        from xl import player
        player.QUEUE._save_player_state(
                os.path.join(xdg.get_data_dir(), 'player.state') )
        player.QUEUE.save_to_location(
                os.path.join(xdg.get_data_dir(), 'queue.state') )
        player.PLAYER.stop()

        from xl import settings
        settings.MANAGER.save()

        if restart:
            logger.info("Restarting...")
            python = sys.executable
            os.execl(python, python, *sys.argv)

        logger.info("Bye!")
        logger_setup.stop_logging()
        sys.exit(0)

def exaile():
    if not Exaile._exaile:
        raise AttributeError(_("Exaile is not yet finished loading"
            ". Perhaps you should listen for the exaile_loaded"
            " signal?"))

    return Exaile._exaile

# vim: et sts=4 sw=4
