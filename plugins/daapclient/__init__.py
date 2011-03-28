# Copyright (C) 2006-2007 Aren Olson
#                    2009 Brian Parma
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

import os
import gtk
import dbus
import dbus.exceptions
import logging
import time
import threading
import gobject
import xlgui
from gettext import gettext as _
from xl import collection, event, trax, common, providers
from xlgui.panel.collection import CollectionPanel
from xlgui import guiutil
from xlgui.widgets import dialogs, menu
from daap import DAAPClient, DAAPError

logger = logging.getLogger(__name__)
gobject.threads_init()

_smi = menu.simple_menu_item
_sep = menu.simple_separator


#
#   Check For python-avahi, we can work without
#  avahi, but wont be able to discover shares.
#

try:
    import avahi
    AVAHI = True
except Exception, inst:
    logger.warn('AVAHI exception: %s' % inst)
    AVAHI = False

# detect authoriztion support in python-daap
try:
    tmp = DAAPClient()
    tmp.connect("spam","eggs","sausage") #dummy login
    del tmp
except TypeError:
    AUTH = False
except:
    AUTH = True

#PLUGIN_ICON = gtk.Button().render_icon(gtk.STOCK_NETWORK, gtk.ICON_SIZE_MENU)

# Globals Warming
MANAGER = None

class DaapAvahiInterface(gobject.GObject): #derived from python-daap/examples
    """
        Handles detection of DAAP shares via Avahi and manages the menu showing the shares.
    Fires a "connect" signal when a menu item is clicked.
    """
    __gsignals__ = {
                    'connect' : ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                                    ( gobject.TYPE_PYOBJECT, ) ) }

    def new_service(self, interface, protocol, name, type, domain, flags):
        interface, protocol, name, type, domain, host, aprotocol, address, port, txt, flags = self.server.ResolveService(interface, protocol, name, type, domain, avahi.PROTO_UNSPEC, dbus.UInt32(0))
        """
            Called when a new share is found.
        """
        logger.info("DAAP: Found %s." % name)
        #Use all available info in key to avoid name conflicts.
        nstr = '%s%s%s%s%s' % (interface, protocol, name, type, domain)

        if name in self.services:   # using only name for conflicts (for multiple adapters)
            return

        self.services[name] = (address, port)
        self.new_share_menu_item(name)

    def remove_service(self, interface, protocol, name, type, domain, flags):
        """
            Called when the connection to a share is lost.
        """
        logger.info("DAAP: Lost %s." % name)
        nstr = '%s%s%s%s%s' % (interface, protocol, name, type, domain)

        if name in self.services:
            self.remove_share_menu_item(name)
            del self.services[name]

    def new_share_menu_item(self, name):
        '''
            This function is called by Avahi when a new share is detected
        on the network.  It adds the share to the Connect menu.
        '''

        if self.menu:
            menu_item = gtk.MenuItem(name)
            menu_item.connect('activate', self.clicked, name )
            self.menu.append_item(menu_item)
            menu_item.show()

    def remove_share_menu_item(self, name):
        '''
            This function is called by Avahi when a share is removed
            from the network.  It removes the menu entry for the share.
        '''

        if self.menu:
            item = [x for x in self.menu.get_children() if (x.get_name() == 'GtkMenuItem') and (unicode(x.get_child().get_text(), 'utf-8') == name)]
            if len(item) > 0:
                item[0].destroy()

    def clicked(self, menu_item, name):
        '''
            This function is called in response to a menu_item click.
        Fire away.
        '''
        gobject.idle_add(self.emit, "connect", (name,)+self.services[name])

    def __init__(self, exaile, menu):
        """
            Sets up the avahi listener.
        """
        gobject.GObject.__init__(self)
        self.services = {}
        self.menu = menu
        self.bus = dbus.SystemBus()
        self.server = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME,
            avahi.DBUS_PATH_SERVER), avahi.DBUS_INTERFACE_SERVER)
        self.stype = '_daap._tcp'
        self.domain = 'local'
        self.browser = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME,
            self.server.ServiceBrowserNew(avahi.IF_UNSPEC, avahi.PROTO_UNSPEC,
            self.stype, self.domain, dbus.UInt32(0))),
            avahi.DBUS_INTERFACE_SERVICE_BROWSER)
        self.browser.connect_to_signal('ItemNew', self.new_service)
        self.browser.connect_to_signal('ItemRemove', self.remove_service)


class DaapManager:
    '''
        DaapManager is a class that manages DaapConnections, both manual
    and avahi-generated.
    '''
    def __init__(self, exaile, menu, avahi):
        '''
            Init!  Create manual menu item, and connect to avahi signal.
        '''
        self.exaile = exaile
        self.avahi = avahi
        self.panels = {}

        menu_item = gtk.MenuItem(_('Manually...'))
        menu_item.connect('activate', self.manual_connect)
        menu.append_item(menu_item)


        if avahi is not None:
            avahi.connect("connect", self.connect_share)

    def connect_share(self, obj, (name, addr, port)):
        '''
            This function is called when a user wants to connec to
        a DAAP share.  It creates a new panel for the share, and
        requests a track list.
        '''

        conn = DaapConnection(name, addr, port)

        conn.connect()
        library = DaapLibrary(conn)
        panel = NetworkPanel(self.exaile.gui.main.window, library, self)
    #    cst = CollectionScanThread(None, panel.net_collection, panel)
    #    cst.start()
        panel.refresh()             # threaded
        xlgui.get_controller().add_panel(*panel.get_panel())
        self.panels[name] = panel

    def disconnect_share(self, name):
        '''
            This function is called to disconnect a previously connected
        share.  It calls the DAAP disconnect, and removes the panel.
        '''

        panel = self.panels[name]
    #    panel.library.daap_share.disconnect()
        panel.daap_share.disconnect()
    #    panel.net_collection.remove_library(panel.library)
        xlgui.get_controller().remove_panel(panel.get_panel()[0])
        del self.panels[name]

    def manual_connect(self, widget):
        '''
            This function is called when the user selects the manual
        connection option from the menu.  It requests a host/ip to connect
        to.
        '''
        dialog = dialogs.TextEntryDialog(
            _("Enter IP address and port for share"),
            _("Enter IP address and port."))
        resp = dialog.run()

        if resp == gtk.RESPONSE_OK:
            loc = dialog.get_value()
            address = str(loc.split(':')[0])
            try:
                port = str(loc.split(':')[1])
            except IndexError:
                port = 3689     # if no port specified, use default DAAP port

            nstr = 'custom%s%s' % (address, port)
    #        print nstr
            conn = DaapConnection(loc, address, port)
            self.connect_share(None, (loc, address, port))

    def refresh_share(self, name):
        panel = self.panels[name]
        rev = panel.daap_share.session.revision
        
        # check for changes
        panel.daap_share.session.update()
        logger.debug('DAAP Server %s returned revision %d ( old: %d ) after update request'
                % (name, panel.daap_share.session.revision, rev))
        
        # if changes, refresh
        if rev != panel.daap_share.session.revision:
            logger.info('DAAP Server %s changed, refreshing... (revision %d)' 
                % (name, panel.daap_share.session.revision))
            panel.refresh()

    def close(self, remove=False):
        '''
            This function disconnects active DaapConnections, and optionally
        removes the panels from the UI.
        '''
        # disconnect active shares
        for panel in self.panels.values():
            panel.daap_share.disconnect()

            # there's no point in doing this if we're just shutting down, only on
            # disable
            if remove:
                xlgui.get_controller().remove_panel(panel.get_panel()[0])


class DaapConnection(object):
    """
        A connection to a DAAP share.
    """
    def __init__(self, name, server, port):
        self.all = []
        self.session = None
        self.connected = False
        self.tracks = None
        self.server = server
        self.port = port
        self.name = name
        self.auth = False
        self.password = None

    def connect(self, password = None):
        """
            Connect, login, and retrieve the track list.
        """
        try:
            client = DAAPClient()
            if AUTH and password:
                client.connect(self.server, self.port, password)
            else:
                client.connect(self.server, self.port)
            self.session = client.login()
            self.connected = True
#        except DAAPError:
        except Exception, inst:
            #print 's:%s, p:%s (%s, %s)' % (self.server, self.port, type(self.server), type(self.port))
            logger.warn('Exception: %s' % inst)
            self.auth = True
            self.connected = False
#            raise DAAPError
            raise Exception, inst

    def disconnect(self):
        """
            Disconnect, clean up.
        """
        try:
            self.session.logout()
        except:
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
        #print 'conversion'
#        t = time.time()
        self.convert_list()
        #print '%f, %d tracks' % (time.time()-t, len(self.all))


    def get_database(self):
        """
            Get a DAAP database and its track list.
        """
        if self.session:
            self.database = self.session.library()
            self.get_tracks(1)

    def get_tracks(self, reset = False):
        """
            Get the track list from a DAAP database
        """
        if reset or self.tracks == None:
            if self.database is None:
                self.database = self.session.library()
            self.tracks = self.database.tracks()

        return self.tracks

    def convert_list(self):
        """
            Converts the DAAP track database into Exaile Tracks.
        """
        # Convert DAAPTrack's attributes to Tracks.
        eqiv = {'title':'minm','artist':'asar','album':'asal','tracknumber':'astn',}
#            'genre':'asgn','enc':'asfm','bitrate':'asbr'}

        for tr in self.tracks:
            if tr is not None:
                #http://<server>:<port>/databases/<dbid>/items/<id>.<type>?session-id=<sessionid>

                uri = "http://%s:%s/databases/%s/items/%s.%s?session-id=%s" % \
                    (self.server, self.port, self.database.id, tr.id,
                    tr.type, self.session.sessionid)

                # Don't scan tracks because gio is slow!
                temp = trax.Track(uri, scan=False)

                for field in eqiv.keys():
                    try:
                        tag = u'%s'%tr.atom.getAtom(eqiv[field])
                        if tag != 'None':
                            temp.set_tag_raw(field, [tag], notify_changed=False)

                    except:
                        if field is 'tracknumber':
                            temp.set_tag_raw('tracknumber', [0], notify_changed=False)
#                        traceback.print_exc(file=sys.stdout)


                #TODO: convert year (asyr) here as well, what's the formula?
                try:
                    temp.set_tag_raw("__length", tr.atom.getAtom('astm') / 1000, notify_changed=False)
                except:
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
                except CannotSendRequest:
                    dialog = gtk.MessageDialog(APP.window,
                        gtk.DIALOG_MODAL, gtk.MESSAGE_INFO, gtk.BUTTONS_OK,
                        _("""This server does not support multiple connections.
You must stop playback before downloading songs."""))


class DaapLibrary(collection.Library):
    '''
        Library subclass for better management of collection??
    Or something to do with devices or somesuch.  Ask Aren.
    '''
    def __init__(self, daap_share, col=None):
#        location = "http://%s:%s/databasese/%s/items/" % (daap_share.server, daap_share.port, daap_share.database.id)
        # Libraries need locations...
        location = "http://%s:%s/" % (daap_share.server, daap_share.port)
        collection.Library.__init__(self, location)
        self.daap_share = daap_share
        #self.collection = col

    def rescan(self, notify_interval=None):
        '''
            Called when a library needs to refresh it's track list.
        '''
        if self.collection is None:
            return True

        if self.scanning:
            return
        t = time.time()
        logger.info('Scanning library: %s' % self.daap_share.name)
        self.scanning = True
        db = self.collection

        # DAAP gives us all the tracks in one dump
        self.daap_share.reload()
        if self.daap_share.all:
            count = len(self.daap_share.all)
        else:
            count = 0

        if count > 0:
            logger.info('Adding %d tracks from %s. (%f s)' % (count, self.daap_share.name, time.time()-t))
            self.collection.add_tracks(self.daap_share.all)


        if notify_interval is not None:
            event.log_event('tracks_scanned', self, count)

        # track removal?
        self.scanning = False
        #return True

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
            Expects a parent gtk.Window, and a daap connection.
        """

        self.name = library.daap_share.name
        self.daap_share = library.daap_share
        self.net_collection = collection.Collection(self.name)
        self.net_collection.add_library(library)
        CollectionPanel.__init__(self, parent, self.net_collection, self.name, _show_collection_empty_message=False)

        self.all = []

        self.connect_id = None

        # Remove the local collection specific menu entries
        kids = self.menu.get_children()
        self.menu.remove(kids[-1])
        self.menu.remove(kids[-2])
        self.menu.remove(kids[-3])

        # Throw a menu entry on the context menu that can disconnect the DAAP share
        self.menu.append(_("Refresh Server List"), lambda x, y: mgr.refresh_share(self.name))
        self.menu.append(_("Disconnect from Server"), lambda x, y: mgr.disconnect_share(self.name))

    @common.threaded
    def refresh(self):
        '''
            This is called to refresh the track list.
        '''
        # Since we don't use a ProgressManager/Thingy, we have to call these w/out
        #  a ScanThread
        self.net_collection.rescan_libraries()
        gobject.idle_add(self._refresh_tags_in_tree)


    def save_selected(self, widget=None, event=None):
        """
            Save the selected tracks to disk.
        """
        items = self.get_selected_items()
        dialog = gtk.FileChooserDialog(_("Select a Location for Saving"),
            APP.window, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            (gtk.STOCK_OPEN, gtk.RESPONSE_OK,
             gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))
        dialog.set_current_folder(APP.get_last_dir())
        dialog.set_select_multiple(False)
        result = dialog.run()
        dialog.hide()

        if result == gtk.RESPONSE_OK:
            folder = dialog.get_current_folder()
            self.save_items(items, folder)

    @common.threaded
    def save_items(self, items, folder):
        for i in items:
            tnum = i.get_track()
            if tnum < 10: tnum = "0%s"%tnum
            else: tnum = str(tnum)
            filename = "%s%s%s - %s.%s"%(folder, os.sep, tnum,
                i.get_title(), i.type)
            i.connection.get_track(i.daapid, filename)
#                print "DAAP: saving track %s to %s."%(i.daapid, filename)


def enable(exaile):
    '''
        Plugin Enabled.
    '''
    if exaile.loading:
        event.add_callback(__enb, 'gui_loaded')
    else:
        __enb(None, exaile, None)

def __enb(eventname, exaile, wat):
    gobject.idle_add(_enable, exaile)

def _enable(exaile):
    global MANAGER

#    if not DAAP:
#        raise Exception("DAAP could not be imported.")

#    if not AVAHI:
#        raise Exception("AVAHI could not be imported.")


    menu = guiutil.Menu()

    providers.register('menubar-tools-menu', _sep('plugin-sep', ['track-properties']))
    
    item = _smi('daap', ['plugin-sep'], _('Connect to DAAP...'),
        submenu=menu)
    providers.register('menubar-tools-menu', item)

    if AVAHI:
        try:
            avahi_interface = DaapAvahiInterface(exaile, menu)
        except RuntimeError: # no dbus?
            avahi_interface = None
            logger.warn('AVAHI interface could not be initialized (no dbus?)')
        except dbus.exceptions.DBusException, s:
            avahi_interface = None
            logger.error('Got DBUS error: %s' % s)
            logger.error('Is avahi-daemon running?')
    else:
        avahi_interface = None
        logger.warn('AVAHI could not be imported, you will not see broadcast shares.')

    MANAGER = DaapManager(exaile, menu, avahi_interface)



def teardown(exaile):
    '''
        Exaile Shutdown.
    '''
    if MANAGER is not None:
        MANAGER.close()


def disable(exaile):
    '''
        Plugin Disabled.
    '''
    # disconnect from active shares
    if MANAGER is not None:
#        MANAGER.clear()
        MANAGER.close(True)

    for item in providers.get('menubar-tools-menu'):
        if item.name == 'daap':
            providers.unregister('menubar-tools-menu', item)
            break

    event.remove_callback(__enb, 'gui_loaded')


# vi: et ts=4 sts=4 sw=4
