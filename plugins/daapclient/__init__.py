# Copyright (C) 2006-2007 Aren Olson
#                    2011 Brian Parma
#                    2020 Rok Mandeljc
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

import functools
from gettext import gettext as _
import http.client
import logging
import pickle
import os
import time

from gi.repository import Gtk
from gi.repository import GObject

from xl import collection, event, trax, common, providers, settings, xdg
from xlgui.panel.collection import CollectionPanel
from xlgui.widgets import dialogs, menu, menuitems
from xlgui import main

from .client import DAAPClient
from . import daapclientprefs


logger = logging.getLogger(__name__)

_smi = menu.simple_menu_item
_sep = menu.simple_separator


# Check for python-zeroconf
try:
    import zeroconf

    ZEROCONF = True
    ZEROCONF_VERSION = [int(v) for v in zeroconf.__version__.split('.')[:2]]

    # ServiceInfo.parsed_addresses() and IPVersion enum were introduced
    # in v.0.24
    ZEROCONF_LEGACY = ZEROCONF_VERSION < [0, 24]
    if ZEROCONF_LEGACY:
        import socket  # for inet_ntoa
except ImportError:
    ZEROCONF = False


# detect authentication support in python-daap
try:
    tmp = DAAPClient()
    tmp.connect("spam", "eggs", "sausage")  # dummy login
    del tmp
except TypeError:
    AUTH = False
except Exception:
    AUTH = True


class DaapZeroconfInterface(GObject.GObject):
    __gsignals__ = {
        'connect': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,))
    }

    def new_share_menu_item(self, menu_name, service_name, address, port):
        """
        This function is called to add a server to the connect menu.
        """

        if not self.menu:
            return

        menu_item = _smi(
            menu_name,
            ['sep'],
            menu_name,
            callback=lambda *_x: self.clicked(service_name, address, port),
        )
        self.menu.add_item(menu_item)

    def clear_share_menu_items(self):
        """
        This function is used to clear all the menu items out of a menu.
        """

        if not self.menu:
            return

        items_to_remove = [
            item
            for item in self.menu._items
            if item.name not in ('manual', 'history', 'sep')
        ]
        for item in items_to_remove:
            self.menu.remove_item(item)

    def rebuild_share_menu_items(self):
        """
        This function fills the menu with known servers.
        """
        self.clear_share_menu_items()

        show_ipv6 = settings.get_option('plugin/daapclient/ipv6', False)
        items = []

        for key, info in self.services.items():
            # Strip the service type from fully-qualified service name
            service_name = info.name
            if service_name.endswith(info.type):
                service_name = service_name[: -(len(info.type) + 1)]

            if ZEROCONF_LEGACY:
                # Legacy mode: returns only a single IPv4 address
                addresses = [socket.inet_ntoa(info.address)]
            else:
                # Retrieve IP address(es)
                if show_ipv6:
                    # Both IPv4 and IPv6
                    addresses = info.parsed_addresses(zeroconf.IPVersion.All)
                else:
                    # IPv4 only
                    addresses = info.parsed_addresses(zeroconf.IPVersion.V4Only)

            # Generate one menu entry for each available address.
            # NOTE: in its current implementation (v.0.25.1), zeroconf
            # appears to always return at most one IPv4 and one IPv6
            # address, even if the service advertises multiple addresses.
            # This appears to be tied to record caching, which keeps
            # track of only the last parsed IPv4 and IPv6 address.
            for address in addresses:
                # gstreamer can't handle link-local ipv6
                if address.startswith('fe80:'):
                    continue

                menu_name = '{0} ({1})'.format(service_name, address)
                items.append((menu_name, service_name, address, info.port))

        # Create menu items
        for item in items:
            self.new_share_menu_item(*item)

    def clicked(self, service_name, address, port):
        """
        This function is called in response to a menu_item click.
        Fire away.
        """
        GObject.idle_add(self.emit, "connect", (service_name, address, port))

    def on_service_state_change(self, service_type, name, state_change, **kwargs):
        # The zeroconf module explicitly passes callback arguments via
        # keywords, and the 'zeroconf' keyword argument clashes with the
        # module name. Hence the ugly work-around via **kwargs...
        zc = kwargs['zeroconf']

        logger.info("DAAP share '{0}': state changed to {1}".format(name, state_change))

        # zeroconf.ServiceStateChange.Updated was introduced in v.0.23
        add_update_states = [zeroconf.ServiceStateChange.Added]
        if hasattr(zeroconf.ServiceStateChange, 'Updated'):
            add_update_states.append(zeroconf.ServiceStateChange.Updated)

        if state_change in add_update_states:
            info = zc.get_service_info(service_type, name)
            if not info:
                return

            self.services[name] = info
        elif state_change is zeroconf.ServiceStateChange.Removed:
            del self.services[name]

        self.rebuild_share_menu_items()

    def __init__(self, _exaile, _menu):
        """
        Sets up the zeroconf listener.
        """
        GObject.GObject.__init__(self)
        self.services = {}
        self.menu = _menu

        if ZEROCONF_LEGACY:
            logger.info("Using zeroconf legacy API")
            zc = zeroconf.Zeroconf()
        else:
            logger.info("Using zeroconf new API")
            zc = zeroconf.Zeroconf(ip_version=zeroconf.IPVersion.All)

        self.browser = zeroconf.ServiceBrowser(
            zc, '_daap._tcp.local.', handlers=[self.on_service_state_change]
        )


class DaapHistory(common.LimitedCache):
    def __init__(self, limit=5, location=None, menu=None, callback=None):
        common.LimitedCache.__init__(self, limit)

        if location is None:
            location = os.path.join(xdg.get_cache_dir(), 'daaphistory.dat')
        self.location = location
        self.menu = menu
        self.callback = callback

        self.load()

    def __setitem__(self, item, value):
        common.LimitedCache.__setitem__(self, item, value)

        # add new menu item
        if self.menu is not None and self.callback is not None:
            menu_item = _smi(
                'hist' + item,
                ['sep'],
                item,
                callback=lambda *_x: self.callback(None, value + (None,)),
            )
            self.menu.add_item(menu_item)

    def load(self):
        try:
            with open(self.location, 'rb') as f:
                try:
                    d = pickle.load(f)
                    self.update(d)
                except (IOError, EOFError):
                    # no file
                    pass
        except (IOError):
            # file not present
            pass

    def save(self):
        with open(self.location, 'wb') as f:
            pickle.dump(self.cache, f, common.PICKLE_PROTOCOL)


class DaapManager:
    """
        DaapManager is a class that manages DaapConnections, both manual
    and auto-discovered.
    """

    def __init__(self, exaile, _menu, autodiscover):
        """
        Init!  Create manual menu item, and connect to interface signal.
        """
        self.exaile = exaile
        self.autodiscover = autodiscover
        self.panels = {}

        hmenu = menu.Menu(None)

        def hmfactory(_menu, _parent, _context):
            item = Gtk.MenuItem.new_with_mnemonic(_('History'))
            item.set_submenu(hmenu)
            sens = settings.get_option('plugin/daapclient/history', True)
            item.set_sensitive(sens)
            return item

        _menu.add_item(
            _smi('manual', [], _('Manually...'), callback=self.manual_connect)
        )
        _menu.add_item(menu.MenuItem('history', hmfactory, ['manual']))
        _menu.add_item(_sep('sep', ['history']))

        if autodiscover is not None:
            autodiscover.connect("connect", self.connect_share)

        self.history = DaapHistory(5, menu=hmenu, callback=self.connect_share)

    def connect_share(self, obj, args):
        """
        This function is called when a user wants to connec to
        a DAAP share.  It creates a new panel for the share, and
        requests a track list.
        `args` is a tuple of (name, address, port, service)
        """
        name, address, port = args  # unpack tuple
        user_agent = self.exaile.get_user_agent_string(__name__)
        conn = DaapConnection(name, address, port, user_agent)

        conn.connect()
        library = DaapLibrary(conn)
        panel = NetworkPanel(self.exaile.gui.main.window, library, self)
        #    cst = CollectionScanThread(None, panel.net_collection, panel)
        #    cst.start()
        panel.refresh()  # threaded
        providers.register('main-panel', panel)
        self.panels[name] = panel

        # history
        if settings.get_option('plugin/daapclient/history', True):
            self.history[name] = (name, address, port)
            self.history.save()

    def disconnect_share(self, name):
        """
        This function is called to disconnect a previously connected
        share.  It calls the DAAP disconnect, and removes the panel.
        """

        panel = self.panels[name]
        #    panel.library.daap_share.disconnect()
        panel.daap_share.disconnect()
        #    panel.net_collection.remove_library(panel.library)
        providers.unregister('main-panel', panel)
        del self.panels[name]

    def manual_connect(self, *_args):
        """
        This function is called when the user selects the manual
        connection option from the menu.  It requests a host/ip to
        connect to.
        """
        dialog = dialogs.TextEntryDialog(
            _("Enter IP address and port for share"), _("Enter IP address and port.")
        )
        resp = dialog.run()

        if resp == Gtk.ResponseType.OK:
            loc = dialog.get_value().strip()
            host = loc

            # the port will be anything after the last :
            p = host.rfind(":")

            # ipv6 literals should have a closing brace before the port
            b = host.rfind("]")

            if p > b:
                try:
                    port = int(host[p + 1 :])
                    host = host[:p]
                except ValueError:
                    logger.error('non-numeric port specified')
                    return
            else:
                port = 3689  # if no port specified, use default DAAP port

            # if it's an ipv6 host with brackets, strip them
            if host and host[0] == '[' and host[-1] == ']':
                host = host[1:-1]
            self.connect_share(None, (loc, host, port, None))

    def refresh_share(self, name):
        panel = self.panels[name]
        rev = panel.daap_share.session.revision

        # check for changes
        panel.daap_share.session.update()
        logger.debug(
            'DAAP Server %s returned revision %d ( old: %d ) after update request'
            % (name, panel.daap_share.session.revision, rev)
        )

        # if changes, refresh
        if rev != panel.daap_share.session.revision:
            logger.info(
                'DAAP Server %s changed, refreshing... (revision %d)'
                % (name, panel.daap_share.session.revision)
            )
            panel.refresh()

    def close(self, remove=False):
        """
        This function disconnects active DaapConnections, and optionally
        removes the panels from the UI.
        """
        # disconnect active shares
        for panel in self.panels.values():
            panel.daap_share.disconnect()

            # there's no point in doing this if we're just shutting down, only on
            # disable
            if remove:
                providers.unregister('main-panel', panel)


class DaapConnection:
    """
    A connection to a DAAP share.
    """

    def __init__(self, name, server, port, user_agent):
        # if it's an ipv6 address
        if ':' in server and server[0] != '[':
            server = '[' + server + ']'

        self.all = []
        self.session = None
        self.connected = False
        self.tracks = None
        self.server = server
        self.port = port
        self.name = name
        self.auth = False
        self.password = None
        self.user_agent = user_agent

    def connect(self, password=None):
        """
        Connect, login, and retrieve the track list.
        """
        try:
            client = DAAPClient()
            if AUTH and password:
                client.connect(self.server, self.port, password, self.user_agent)
            else:
                client.connect(self.server, self.port, None, self.user_agent)
            self.session = client.login()
            self.connected = True
        #        except DAAPError:
        except Exception:
            logger.exception(
                'failed to connect to ({0},{1})'.format(self.server, self.port)
            )

            self.auth = True
            self.connected = False
            raise

    def disconnect(self):
        """
        Disconnect, clean up.
        """
        try:
            self.session.logout()
        except Exception:
            pass
        self.session = None
        self.tracks = None
        self.database = None
        self.all = []
        self.connected = False

    def reload(self):
        """
        Reload the tracks from the server
        """
        self.tracks = None
        self.database = None
        self.all = []
        self.get_database()

        t = time.time()
        self.convert_list()
        logger.debug('{0} tracks loaded in {1}s'.format(len(self.all), time.time() - t))

    def get_database(self):
        """
        Get a DAAP database and its track list.
        """
        if self.session:
            self.database = self.session.library()
            self.get_tracks(1)

    def get_tracks(self, reset=False):
        """
        Get the track list from a DAAP database
        """
        if reset or self.tracks is None:
            if self.database is None:
                self.database = self.session.library()
            self.tracks = self.database.tracks()

        return self.tracks

    def convert_list(self):
        """
        Converts the DAAP track database into Exaile Tracks.
        """
        # Convert DAAPTrack's attributes to Tracks.
        eqiv = {
            'title': 'minm',
            'artist': 'asar',
            'album': 'asal',
            'tracknumber': 'astn',
            'date': 'asyr',
            'discnumber': 'asdn',
            'albumartist': 'asaa',
        }
        #            'genre':'asgn','enc':'asfm','bitrate':'asbr'}

        for tr in self.tracks:
            if tr is not None:
                # http://<server>:<port>/databases/<dbid>/items/<id>.<type>?session-id=<sessionid>

                uri = "http://%s:%s/databases/%s/items/%s.%s?session-id=%s" % (
                    self.server,
                    self.port,
                    self.database.id,
                    tr.id,
                    tr.type,
                    self.session.sessionid,
                )

                # Don't scan tracks because gio is slow!
                temp = trax.Track(uri, scan=False)

                for field in eqiv.keys():
                    try:
                        tag = '%s' % tr.atom.getAtom(eqiv[field])
                        if tag != 'None':
                            temp.set_tag_raw(field, [tag], notify_changed=False)

                    except Exception:
                        if field == 'tracknumber':
                            temp.set_tag_raw('tracknumber', [0], notify_changed=False)

                # TODO: convert year (asyr) here as well, what's the formula?
                try:
                    temp.set_tag_raw(
                        "__length",
                        tr.atom.getAtom('astm') // 1000,
                        notify_changed=False,
                    )
                except Exception:
                    temp.set_tag_raw("__length", 0, notify_changed=False)

                self.all.append(temp)

    @common.threaded
    def get_track(self, track_id, filename):
        """
        Save the track with track_id to filename
        """
        for t in self.tracks:
            if t.id == track_id:
                try:
                    t.save(filename)
                except http.client.CannotSendRequest:
                    Gtk.MessageDialog(
                        buttons=Gtk.ButtonsType.OK,
                        message_type=Gtk.MessageType.INFO,
                        modal=True,
                        text=_(
                            """This server does not support multiple connections.
You must stop playback before downloading songs."""
                        ),
                        transient_for=main.mainwindow().window,
                    )
                    return


class DaapLibrary(collection.Library):
    """
    Library subclass for better management of collection??
    Or something to do with devices or somesuch. Ask Aren.
    """

    def __init__(self, daap_share, col=None):
        #        location = "http://%s:%s/databasese/%s/items/" % (daap_share.server, daap_share.port, daap_share.database.id)
        # Libraries need locations...
        location = "http://%s:%s/" % (daap_share.server, daap_share.port)
        collection.Library.__init__(self, location)
        self.daap_share = daap_share
        # self.collection = col

    def rescan(self, notify_interval=None, force_update=False):
        """
        Called when a library needs to refresh its track list.

        The force_update parameter is not applicable and is ignored.
        """
        if self.collection is None:
            return True

        if self.scanning:
            return
        t = time.time()
        logger.info('Scanning library: %s' % self.daap_share.name)
        self.scanning = True

        # DAAP gives us all the tracks in one dump
        self.daap_share.reload()
        if self.daap_share.all:
            count = len(self.daap_share.all)
        else:
            count = 0

        if count > 0:
            logger.info(
                'Adding %d tracks from %s. (%f s)'
                % (count, self.daap_share.name, time.time() - t)
            )
            self.collection.add_tracks(self.daap_share.all)

        if notify_interval is not None:
            event.log_event('tracks_scanned', self, count)

        # track removal?
        self.scanning = False
        # return True

    # Needed to be overriden for who knows why (exceptions)
    def _count_files(self):
        count = 0
        if self.daap_share:
            count = len(self.daap_share.all)

        return count


class NetworkPanel(CollectionPanel):
    """
    A panel that displays a collection of tracks from the DAAP share.
    """

    def __init__(self, parent, library, mgr):
        """
        Expects a parent Gtk.Window, and a daap connection.
        """

        self.name = str(library.daap_share.name)
        self.daap_share = library.daap_share
        self.net_collection = collection.Collection(self.name)
        self.net_collection.add_library(library)
        CollectionPanel.__init__(
            self,
            parent,
            self.net_collection,
            self.name,
            _show_collection_empty_message=False,
            label=self.name,
        )

        self.all = []

        self.connect_id = None

        self.menu = menu.Menu(self)

        def get_tracks_func(*_args):
            return self.tree.get_selected_tracks()

        self.menu.add_item(menuitems.AppendMenuItem('append', [], get_tracks_func))
        self.menu.add_item(
            menuitems.EnqueueMenuItem('enqueue', ['append'], get_tracks_func)
        )
        self.menu.add_item(
            menuitems.PropertiesMenuItem('props', ['enqueue'], get_tracks_func)
        )
        self.menu.add_item(_sep('sep', ['props']))
        self.menu.add_item(
            _smi(
                'refresh',
                ['sep'],
                _('Refresh Server List'),
                callback=lambda *x: mgr.refresh_share(self.name),
            )
        )
        self.menu.add_item(
            _smi(
                'disconnect',
                ['refresh'],
                _('Disconnect from Server'),
                callback=lambda *x: mgr.disconnect_share(self.name),
            )
        )

    @common.threaded
    def refresh(self):
        """
        This is called to refresh the track list.
        """
        # Since we don't use a ProgressManager/Thingy, we have to call these w/out
        #  a ScanThread
        self.net_collection.rescan_libraries()
        GObject.idle_add(self._refresh_tags_in_tree)

    def save_selected(self, widget=None, event=None):
        """
        Save the selected tracks to disk.
        """
        items = self.get_selected_items()
        dialog = Gtk.FileChooserDialog(
            _("Select a Location for Saving"),
            main.mainwindow().window,
            Gtk.FileChooserAction.SELECT_FOLDER,
            (
                Gtk.STOCK_OPEN,
                Gtk.ResponseType.OK,
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
            ),
        )
        dialog.set_current_folder(xdg.get_last_dir())
        dialog.set_select_multiple(False)
        result = dialog.run()
        dialog.hide()

        if result == Gtk.ResponseType.OK:
            folder = dialog.get_current_folder()
            self.save_items(items, folder)

    @common.threaded
    def save_items(self, items, folder):
        for i in items:
            tnum = i.get_track()
            if tnum < 10:
                tnum = "0%s" % tnum
            else:
                tnum = str(tnum)
            filename = "%s%s%s - %s.%s" % (folder, os.sep, tnum, i.get_title(), i.type)
            i.connection.get_track(i.daapid, filename)


#                print "DAAP: saving track %s to %s."%(i.daapid, filename)


class DaapClientPlugin:

    __exaile = None
    __manager = None

    def enable(self, exaile):
        """
        Plugin Enabled.
        """
        self.__exaile = exaile

    def on_gui_loaded(self):
        event.add_callback(self.__on_settings_changed, 'plugin_daapclient_option_set')

        menu_ = menu.Menu(None)

        providers.register(
            'menubar-tools-menu', _sep('plugin-sep', ['track-properties'])
        )

        item = _smi('daap', ['plugin-sep'], _('Connect to DAAP...'), submenu=menu_)
        providers.register('menubar-tools-menu', item)

        autodiscover = None
        if ZEROCONF:
            try:
                autodiscover = DaapZeroconfInterface(self.__exaile, menu_)
            except RuntimeError:
                logger.warning('zeroconf interface could not be initialized')
        else:
            logger.warning(
                'python-zeroconf is not available; disabling DAAP share auto-discovery!'
            )

        self.__manager = DaapManager(self.__exaile, menu_, autodiscover)

    def teardown(self, exaile):
        """
        Exaile Shutdown.
        """
        # disconnect from active shares
        if self.__manager is not None:
            self.__manager.close()
            self.__manager = None

    def disable(self, exaile):
        """
        Plugin Disabled.
        """
        self.teardown(exaile)

        for item in providers.get('menubar-tools-menu'):
            if item.name == 'daap':
                providers.unregister('menubar-tools-menu', item)
                break

    def get_preferences_pane(self):
        return daapclientprefs

    def __on_settings_changed(self, event, setting, option):
        if option == 'plugin/daapclient/ipv6' and self.__manager is not None:
            self.__manager.autodiscover.rebuild_share_menu_items()


plugin_class = DaapClientPlugin

# vi: et ts=4 sts=4 sw=4
