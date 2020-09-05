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
# Holds the main Exaile class, whose instantiation starts up the entirety
# of Exaile and which also handles Exaile shutdown.
#
# Also takes care of parsing commandline options.

import os
import platform
import sys
import threading

from xl import logger_setup
from xl.externals.sigint import InterruptibleLoopContext
from xl.nls import gettext as _

# Imported later to avoid PyGObject imports just for --help.
GLib = Gio = Gtk = common = xdg = None


def _do_heavy_imports():
    global GLib, Gio, Gtk, common, xdg

    import gi

    gi.require_version('Gdk', '3.0')
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gst', '1.0')
    gi.require_version('GIRepository', '2.0')
    gi.require_version('GstPbutils', '1.0')

    from gi.repository import GLib, Gio, Gtk
    from xl import common, xdg


# placeholder, - xl.version can be slow to import, which would slow down
# cli args. Thus we import __version__ later.
__version__ = None

logger = None


def create_argument_parser():
    """Create command-line argument parser for Exaile"""

    import argparse

    # argparse hard-codes "usage:" uncapitalized. We replace this with an
    # empty string and put "Usage:" in the actual usage string instead.

    class Formatter(argparse.HelpFormatter):
        def _format_usage(self, usage, actions, groups, prefix):
            return super(self.__class__, self)._format_usage(usage, actions, groups, "")

    p = argparse.ArgumentParser(
        usage=_("Usage: exaile [OPTION...] [LOCATION...]"),
        description=_(
            "Launch Exaile, optionally adding tracks specified by"
            " LOCATION to the active playlist."
            " If Exaile is already running, this attempts to use the existing"
            " instance instead of creating a new one."
        ),
        add_help=False,
        formatter_class=Formatter,
    )

    p.add_argument('locs', nargs='*', help=argparse.SUPPRESS)

    group = p.add_argument_group(_('Playback Options'))
    group.add_argument(
        "-n",
        "--next",
        dest="Next",
        action="store_true",
        default=False,
        help=_("Play the next track"),
    )
    group.add_argument(
        "-p",
        "--prev",
        dest="Prev",
        action="store_true",
        default=False,
        help=_("Play the previous track"),
    )
    group.add_argument(
        "-s",
        "--stop",
        dest="Stop",
        action="store_true",
        default=False,
        help=_("Stop playback"),
    )
    group.add_argument(
        "-a", "--play", dest="Play", action="store_true", default=False, help=_("Play")
    )
    group.add_argument(
        "-u",
        "--pause",
        dest="Pause",
        action="store_true",
        default=False,
        help=_("Pause"),
    )
    group.add_argument(
        "-t",
        "--play-pause",
        dest="PlayPause",
        action="store_true",
        default=False,
        help=_("Pause or resume playback"),
    )
    group.add_argument(
        "--stop-after-current",
        dest="StopAfterCurrent",
        action="store_true",
        default=False,
        help=_("Stop playback after current track"),
    )

    group = p.add_argument_group(_('Collection Options'))
    group.add_argument(
        "--add",
        dest="Add",
        # TRANSLATORS: Meta variable for --add and --export-playlist
        metavar=_("LOCATION"),
        help=_("Add tracks from LOCATION to the collection"),
    )

    group = p.add_argument_group(_('Playlist Options'))
    group.add_argument(
        "--export-playlist",
        dest="ExportPlaylist",
        # TRANSLATORS: Meta variable for --add and --export-playlist
        metavar=_("LOCATION"),
        help=_('Export the current playlist to LOCATION'),
    )

    group = p.add_argument_group(_('Track Options'))
    group.add_argument(
        "-q",
        "--query",
        dest="Query",
        action="store_true",
        default=False,
        help=_("Query player"),
    )
    group.add_argument(
        "--format-query",
        dest="FormatQuery",
        # TRANSLATORS: Meta variable for --format-query
        metavar=_('FORMAT'),
        help=_('Retrieve the current playback state and track information as FORMAT'),
    )
    group.add_argument(
        "--format-query-tags",
        dest="FormatQueryTags",
        # TRANSLATORS: Meta variable for --format-query-tags
        metavar=_('TAGS'),
        help=_('Tags to retrieve from the current track; use with --format-query'),
    )
    group.add_argument(
        "--gui-query",
        dest="GuiQuery",
        action="store_true",
        default=False,
        help=_("Show a popup with data of the current track"),
    )
    group.add_argument(
        "--get-title",
        dest="GetTitle",
        action="store_true",
        default=False,
        help=_("Print the title of current track"),
    )
    group.add_argument(
        "--get-album",
        dest="GetAlbum",
        action="store_true",
        default=False,
        help=_("Print the album of current track"),
    )
    group.add_argument(
        "--get-artist",
        dest="GetArtist",
        action="store_true",
        default=False,
        help=_("Print the artist of current track"),
    )
    group.add_argument(
        "--get-length",
        dest="GetLength",
        action="store_true",
        default=False,
        help=_("Print the length of current track"),
    )
    group.add_argument(
        '--set-rating',
        dest="SetRating",
        type=int,
        # TRANSLATORS: Variable for command line options with arguments
        metavar=_('N'),
        help=_('Set rating for current track to N%').replace("%", "%%"),
    )
    group.add_argument(
        '--get-rating',
        dest='GetRating',
        action='store_true',
        default=False,
        help=_('Get rating for current track'),
    )
    group.add_argument(
        "--current-position",
        dest="CurrentPosition",
        action="store_true",
        default=False,
        help=_("Print the current playback position as time"),
    )
    group.add_argument(
        "--current-progress",
        dest="CurrentProgress",
        action="store_true",
        default=False,
        help=_("Print the current playback progress as percentage"),
    )

    group = p.add_argument_group(_('Volume Options'))
    group.add_argument(
        "-i",
        "--increase-vol",
        dest="IncreaseVolume",
        type=int,
        # TRANSLATORS: Meta variable for --increase-vol and--decrease-vol
        metavar=_("N"),
        help=_("Increase the volume by N%").replace("%", "%%"),
    )
    group.add_argument(
        "-l",
        "--decrease-vol",
        dest="DecreaseVolume",
        type=int,
        # TRANSLATORS: Meta variable for --increase-vol and--decrease-vol
        metavar=_("N"),
        help=_("Decrease the volume by N%").replace("%", "%%"),
    )
    group.add_argument(
        "-m",
        "--toggle-mute",
        dest="ToggleMute",
        action="store_true",
        default=False,
        help=_("Mute or unmute the volume"),
    )
    group.add_argument(
        "--get-volume",
        dest="GetVolume",
        action="store_true",
        default=False,
        help=_("Print the current volume percentage"),
    )

    group = p.add_argument_group(_('Other Options'))
    group.add_argument(
        "--new",
        dest="NewInstance",
        action="store_true",
        default=False,
        help=_("Start new instance"),
    )
    group.add_argument(
        "-h", "--help", action="help", help=_("Show this help message and exit")
    )
    group.add_argument(
        "--version",
        dest="ShowVersion",
        action="store_true",
        help=_("Show program's version number and exit."),
    )
    group.add_argument(
        "--start-minimized",
        dest="StartMinimized",
        action="store_true",
        default=False,
        help=_("Start minimized (to tray, if possible)"),
    )
    group.add_argument(
        "--toggle-visible",
        dest="GuiToggleVisible",
        action="store_true",
        default=False,
        help=_("Toggle visibility of the GUI (if possible)"),
    )
    group.add_argument(
        "--safemode",
        dest="SafeMode",
        action="store_true",
        default=False,
        help=_(
            "Start in safe mode - sometimes" " useful when you're running into problems"
        ),
    )
    group.add_argument(
        "--force-import",
        dest="ForceImport",
        action="store_true",
        default=False,
        help=_(
            "Force import of old data" " from version 0.2.x (overwrites current data)"
        ),
    )
    group.add_argument(
        "--no-import",
        dest="NoImport",
        action="store_true",
        default=False,
        help=_("Do not import old data" " from version 0.2.x"),
    )
    group.add_argument(
        "--start-anyway",
        dest="StartAnyway",
        action="store_true",
        default=False,
        help=_("Make control options like" " --play start Exaile if it is not running"),
    )

    group = p.add_argument_group(_('Development/Debug Options'))
    group.add_argument(
        "--datadir",
        dest="UseDataDir",
        metavar=_('DIRECTORY'),
        help=_("Set data directory"),
    )
    group.add_argument(
        "--all-data-dir",
        dest="UseAllDataDir",
        metavar=_('DIRECTORY'),
        help=_("Set data and config directory"),
    )
    group.add_argument(
        "--modulefilter",
        dest="ModuleFilter",
        metavar=_('MODULE'),
        help=_('Limit log output to MODULE'),
    )
    group.add_argument(
        "--levelfilter",
        dest="LevelFilter",
        metavar=_('LEVEL'),
        help=_('Limit log output to LEVEL'),
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
    )
    group.add_argument(
        "--debug",
        dest="Debug",
        action="store_true",
        default=False,
        help=_("Show debugging output"),
    )
    group.add_argument(
        "--eventdebug",
        dest="DebugEvent",
        action="store_true",
        default=False,
        help=_("Enable debugging of" " xl.event. Generates lots of output"),
    )
    group.add_argument(
        "--eventdebug-full",
        dest="DebugEventFull",
        action="store_true",
        default=False,
        help=_("Enable full debugging of" " xl.event. Generates LOTS of output"),
    )
    group.add_argument(
        "--threaddebug",
        dest="DebugThreads",
        action="store_true",
        default=False,
        help=_("Add thread name to logging" " messages."),
    )
    group.add_argument(
        "--eventfilter",
        dest="EventFilter",
        metavar=_('TYPE'),
        help=_("Limit xl.event debug to output of TYPE"),
    )
    group.add_argument(
        "--quiet",
        dest="Quiet",
        action="store_true",
        default=False,
        help=_("Reduce level of output"),
    )
    group.add_argument(
        '--startgui', dest='StartGui', action='store_true', default=False
    )
    group.add_argument(
        '--no-dbus',
        dest='Dbus',
        action='store_false',
        default=True,
        help=_("Disable D-Bus support"),
    )
    group.add_argument(
        '--no-hal',
        dest='Hal',
        action='store_false',
        default=True,
        help=_("Disable HAL support."),
    )

    return p


class Exaile:
    _exaile = None

    def __init__(self):
        """
        Initializes Exaile.
        """
        self.quitting = False
        self.loading = True

        # NOTE: This automatically exits on --help.
        self.options = create_argument_parser().parse_args()

        if self.options.ShowVersion:
            self.version()
            return

        _do_heavy_imports()

        # Set program name for matching with .desktop file in Plasma
        # under wayland (see #653); should be done before splash screen
        # is displayed.
        GLib.set_prgname('exaile')

        if self.options.UseDataDir:
            xdg.data_dirs.insert(1, self.options.UseDataDir)

        # this is useful on Win32, because you cannot set these directories
        # via environment variables
        if self.options.UseAllDataDir:
            alldatadir = self.options.UseAllDataDir

            # TODO: is this still necessary? Python3 does not seem to
            # have issue with UTF-8 characters in path (in contrast
            # to Python2, os.path.join() does not fail).
            # For now, we replace the UTF-8 characters with ? to keep
            # the behavior consistent with the old version...
            if not os.path.supports_unicode_filenames:
                try:
                    alldatadir.encode('ascii')
                except UnicodeEncodeError:
                    # Replace non-ASCII characters with ?
                    alldatadir = alldatadir.encode('ascii', 'replace').decode('ascii')
                    print(
                        "WARNING : converted non-ASCII data dir %s to ascii: %s"
                        % (self.options.UseAllDataDir, alldatadir)
                    )
            xdg.data_home = alldatadir
            xdg.data_dirs.insert(0, xdg.data_home)
            xdg.config_home = alldatadir
            xdg.config_dirs.insert(0, xdg.config_home)
            xdg.cache_home = alldatadir

        try:
            xdg._make_missing_dirs()
        except OSError as e:
            print(
                'ERROR: Could not create configuration directories: %s' % e,
                file=sys.stderr,
            )
            return

        # Make event debug imply debug
        if self.options.DebugEventFull:
            self.options.DebugEvent = True

        if self.options.DebugEvent:
            self.options.Debug = True

        try:
            logger_setup.start_logging(
                self.options.Debug,
                self.options.Quiet,
                self.options.DebugThreads,
                self.options.ModuleFilter,
                self.options.LevelFilter,
            )
        except OSError as e:
            print('ERROR: could not setup logging: %s' % e, file=sys.stderr)
            return

        global logger
        import logging

        logger = logging.getLogger(__name__)

        try:
            # Late import ensures xl.event uses correct logger
            from xl import event

            if self.options.EventFilter:
                event.EVENT_MANAGER.logger_filter = self.options.EventFilter
                self.options.DebugEvent = True

            if self.options.DebugEvent:
                event.EVENT_MANAGER.use_logger = True

            if self.options.DebugEventFull:
                event.EVENT_MANAGER.use_verbose_logger = True

            # initial mainloop setup. The actual loop is started later,
            # if necessary
            self.mainloop_init()

            # initialize DbusManager
            if self.options.StartGui and self.options.Dbus:
                from xl import xldbus

                exit = xldbus.check_exit(self.options, self.options.locs)
                if exit == "exit":
                    sys.exit(0)
                elif exit == "command":
                    if not self.options.StartAnyway:
                        sys.exit(0)
                self.dbus = xldbus.DbusManager(self)

            # import version, see note above
            global __version__
            from xl.version import __version__

            # load the rest.
            self.__init()

            # handle delayed commands
            if (
                self.options.StartGui
                and self.options.Dbus
                and self.options.StartAnyway
                and exit == "command"
            ):
                xldbus.run_commands(self.options, self.dbus)

            # connect dbus signals
            if self.options.StartGui and self.options.Dbus:
                self.dbus._connect_signals()

            # On SIGTERM, quit normally.
            import signal

            signal.signal(signal.SIGTERM, (lambda sig, stack: self.quit()))

            # run the GUIs mainloop, if needed
            if self.options.StartGui:
                # Handle keyboard interruptions
                with InterruptibleLoopContext(self.quit):
                    Gtk.main()  # mainloop
        except Exception:
            logger.exception("Unhandled exception")

    def __init(self):
        """
        Initializes Exaile
        """

        logger.info("Loading Exaile %s...", __version__)

        from gi.repository import GObject
        from .version import register

        register('Python', platform.python_version())
        register('PyGObject', '%d.%d.%d' % GObject.pygobject_version)

        logger.info("Loading settings...")
        try:
            from xl import settings
        except common.VersionError:
            logger.exception("Error loading settings")
            sys.exit(1)

        logger.debug("Settings loaded from %s", settings.location)

        # display locale information if available
        try:
            import locale

            lc, enc = locale.getlocale()
            if enc is not None:
                locale_str = '%s %s' % (lc, enc)
            else:
                locale_str = _('Unknown')

            register('Locale', locale_str)
        except Exception:
            pass

        splash = None

        if self.options.StartGui:
            if settings.get_option('gui/use_splash', True):
                from xlgui.widgets.info import Splash

                splash = Splash()
                splash.show()

        firstrun = settings.get_option("general/first_run", True)

        # Migrate old rating options
        from xl.migrations.settings import rating

        rating.migrate()

        # Migrate builtin OSD to plugin
        from xl.migrations.settings import osd

        osd.migrate()

        # Migrate engines
        from xl.migrations.settings import engine

        engine.migrate()

        # TODO: enable audio plugins separately from normal
        #       plugins? What about plugins that use the player?

        # Gstreamer doesn't initialize itself automatically, and fails
        # miserably when you try to inherit from something and GST hasn't
        # been initialized yet. So this is here.
        from gi.repository import Gst

        Gst.init(None)

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
            self.collection = collection.Collection(
                "Collection", location=os.path.join(xdg.get_data_dir(), 'music.db')
            )
        except common.VersionError:
            logger.exception("VersionError loading collection")
            sys.exit(1)

        # Migrate covers.db. This can only be done after the collection is loaded.
        import xl.migrations.database.covers_1to2 as mig

        mig.migrate()

        from xl import event

        # Set up the player and playback queue
        from xl import player

        event.log_event("player_loaded", player.PLAYER, None)

        # Initalize playlist manager
        from xl import playlist

        self.playlists = playlist.PlaylistManager()
        self.smart_playlists = playlist.SmartPlaylistManager(
            'smart_playlists', collection=self.collection
        )
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

        if self.options.Hal:
            from xl import hal

            udisks2 = hal.UDisks2(self.devices)
            if udisks2.connect():
                self.udisks2 = udisks2

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

        if firstrun:
            settings.set_option("general/first_run", False)

        self.loading = False
        Exaile._exaile = self
        event.log_event("exaile_loaded", self, None)

        restore = True

        if self.gui:
            # Find out if the user just passed in a list of songs
            # TODO: find a better place to put this

            songs = [Gio.File.new_for_path(arg).get_uri() for arg in self.options.locs]
            if len(songs) > 0:
                restore = False
                self.gui.open_uri(songs[0], play=True)
                for arg in songs[1:]:
                    self.gui.open_uri(arg)

            # kick off autoscan of libraries
            # -> don't do it in command line mode, since that isn't expected
            self.gui.rescan_collection_with_progress(True)

        if restore:
            player.QUEUE._restore_player_state(
                os.path.join(xdg.get_data_dir(), 'player.state')
            )

        # pylint: enable-msg=W0201

    def version(self):
        from xl.version import __version__

        print("Exaile", __version__)
        sys.exit(0)

    def _add_default_playlists(self):
        """
        Adds some default smart playlists to the playlist manager
        """
        from xl import playlist

        # entire playlist
        entire_lib = playlist.SmartPlaylist(
            _("Entire Library"), collection=self.collection
        )
        self.smart_playlists.save_playlist(entire_lib, overwrite=True)

        # random playlists
        for count in (100, 300, 500):
            pl = playlist.SmartPlaylist(
                _("Random %d") % count, collection=self.collection
            )
            pl.set_return_limit(count)
            pl.set_random_sort(True)
            self.smart_playlists.save_playlist(pl, overwrite=True)

        # rating based playlists
        for item in (3, 4):
            pl = playlist.SmartPlaylist(
                _("Rating > %d") % item, collection=self.collection
            )
            pl.add_param('__rating', '>', item)
            self.smart_playlists.save_playlist(pl, overwrite=True)

    def mainloop_init(self):
        from gi.repository import GObject

        MIN_VER = (3, 10, 2)
        ver = GObject.pygobject_version

        if ver < MIN_VER:
            # Probably should exit?
            logger.warning(
                "Exaile requires PyGObject %d.%d.%d or greater! (got %d.%d.%d)",
                *(MIN_VER + ver)
            )

        if self.options.Dbus:
            import dbus
            import dbus.mainloop.glib

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
        while True:
            try:
                context.iteration(True)
            except Exception:
                pass

    def get_version(self):
        """
        Returns the current version
        """
        return __version__

    def get_user_agent_string(self, plugin_name=None):
        """
        Returns an appropriately formatted User-agent string for
        web requests. When possible, plugins should use this to
        format user agent strings.

        Users can control this agent string by manually setting
        general/user_agent and general/user_agent_w_plugin in settings.ini

        :param plugin_name: the name of the plugin
        """

        version = __version__
        if '+' in version:  # strip out revision identifier
            version = version[: version.index('+')]

        fmt = {'version': version}

        if not hasattr(self, '_user_agent_no_plugin'):

            from xl import settings

            default_no_plugin = 'Exaile/%(version)s (+https://www.exaile.org)'
            default_plugin = 'Exaile/%(version)s %(plugin_name)s/%(plugin_version)s (+https://www.exaile.org)'

            self._user_agent_no_plugin = settings.get_option(
                'general/user_agent', default_no_plugin
            )
            self._user_agent_w_plugin = settings.get_option(
                'general/user_agent_w_plugin', default_plugin
            )

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

        logger.info("Tearing down plugins...")
        self.plugins.teardown(self)

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
            os.path.join(xdg.get_data_dir(), 'player.state')
        )
        player.QUEUE.save_to_location(os.path.join(xdg.get_data_dir(), 'queue.state'))
        player.PLAYER.stop()

        from xl import settings

        settings.MANAGER.save()

        if restart:
            logger.info("Restarting...")
            logger_setup.stop_logging()
            python = sys.executable
            if sys.platform == 'win32':
                # Python Win32 bug: it does not quote individual command line
                # arguments. Here we do it ourselves and pass the whole thing
                # as one string.
                # See https://bugs.python.org/issue436259 (closed wontfix).
                import subprocess

                cmd = [python] + sys.argv
                cmd = subprocess.list2cmdline(cmd)
                os.execl(python, cmd)
            else:
                os.execl(python, python, *sys.argv)

        logger.info("Bye!")
        logger_setup.stop_logging()
        sys.exit(0)


def exaile():
    if not Exaile._exaile:
        raise AttributeError(
            _(
                "Exaile is not yet finished loading"
                ". Perhaps you should listen for the exaile_loaded"
                " signal?"
            )
        )

    return Exaile._exaile


# vim: et sts=4 sw=4
