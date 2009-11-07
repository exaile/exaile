# Copyright (C) 2006-2007 Aren Olson
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

import os, gtk, dbus, logging, time, threading
from gettext import gettext as _
import gobject
from xl import collection, event, track, common
from xlgui.panel.collection import CollectionPanel
import xlgui
from xlgui import guiutil, commondialogs
from xlgui.collection import CollectionScanThread

logger = logging.getLogger(__name__)
gobject.threads_init()

try:
    from daap import DAAPClient, DAAPError
    DAAP = True
except Exception as inst:
    logger.warn('DAAP exception: %s' % inst)
    DAAP = False

#detect authoriztion support in python-daap
if DAAP:
    try:
        tmp = DAAPClient()
        tmp.connect("spam","eggs","sausage") #dummy login
        del tmp
    except TypeError:
        AUTH = False
    except:
        AUTH = True

try:
    import avahi
    AVAHI = True
except Exception as inst:
    logger.warn('AVAHI exception: %s' % inst)
    AVAHI = False

#PLUGIN_ICON = gtk.Button().render_icon('gtk-network', gtk.ICON_SIZE_MENU)

PANELS = {}
MENU_ITEM = None
AVAHI_INTERFACE = None

def new_share(conn, exaile, menu):
    if menu:
        menu_item = gtk.MenuItem(conn.name)
        menu_item.connect('activate', lambda x : connect_share(conn, exaile.gui.main.window) )
        menu.append_item(menu_item)
        menu_item.show()
    
def remove_share(conn, menu):
    label = conn.name
    if menus:
        item = [x for x in menus.get_children() if (x.get_name() == 'GtkMenuItem') and (unicode(x.get_child().get_text(), 'utf-8') == label)]
        if len(item) > 0:
            item[0].destroy()

def connect_share(conn, parent):
    global PANELS
    
    conn.connect()
#    library = DAAPLibrary(conn)
    panel = NetworkPanel(parent, conn)
#    panel.net_collection.rescan_libraries()
#    cst = CollectionScanThread(None, panel.net_collection, panel)
#    cst.start()
    panel.refresh()
#    panel.refresh()
    xlgui.controller().add_panel(*panel.get_panel())
    PANELS[conn.name] = panel
    
def disconnect_share(conn):
    global PANELS

    panel = PANELS[conn.name]
#    panel.library.active_share.disconnect()
    panel.daap_share.disconnect()
#    panel.net_collection.remove_library(panel.library)
    xlgui.controller().remove_panel(panel.get_panel()[0])
    del PANELS[conn.name]

def manual_connect(widget, exaile):
    dialog = commondialogs.TextEntryDialog(
        _("Enter IP address and port for share"),
        _("Enter IP address and port."))
    resp = dialog.run()
        
    if resp == gtk.RESPONSE_OK:
        loc = dialog.get_value()
        address = str(loc.split(':')[0])
        try:
            port = str(loc.split(':')[1])
        except IndexError:
            port = 3689
                
        nstr = 'custom%s%s' % (address, port)
#        print nstr
        conn = DaapConnection(loc, address, port)
        connect_share(conn, exaile.gui.main.window)
            


class DaapAvahiInterface: #derived from python-daap/examples
    """
        Handles detection of DAAP shares via Avahi.
    """

    def new_service(self, interface, protocol, name, type, domain, flags):
        interface, protocol, name, type, domain, host, aprotocol, address, port, txt, flags = self.server.ResolveService(interface, protocol, name, type, domain, avahi.PROTO_UNSPEC, dbus.UInt32(0))
        """
            Called when a new share is found.
        """
        logger.info("DAAP: Found %s." % name)
        #Use all available info in key to avoid name conflicts.
        nstr = '%s%s%s%s%s' % (interface, protocol, name, type, domain)
        if name in self.services:
            return
        conn = DaapConnection(name, address, port)
        self.services[name] = conn
        new_share(conn, self.exaile, self.menu)
#        self.panel.update_connections()

    def remove_service(self, interface, protocol, name, type, domain, flags):
        """
            Called when the connection to a share is lost.
        """
        logger.info("DAAP: Lost %s." % name)
        nstr = '%s%s%s%s%s' % (interface, protocol, name, type, domain)
        conn = self.services[name]
        remove_share(conn, self.menu)        
        del self.services[name]
#        self.panel.update_connections()

    def __init__(self, exaile, menu):
        """
            Sets up the avahi listener.
        """
        self.exaile = exaile
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

class DaapConnection(object):
    """
        A connection to a DAAP share.
    """
    def __init__(self, name, server, port):
        self.all = []#library.TrackData()
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
        except Exception as inst:
            #print 's:%s, p:%s (%s, %s)' % (self.server, self.port, type(self.server), type(self.port))
            logger.warn(print 'Exception: %s' % inst)
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
        t = time.time()
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
            Converts the DAAP track database into DaapTracks.
        """
        # Convert DAAPTrack's attributes to media.Track's.
        eqiv = {'title':'minm','artist':'asar','album':'asal','track':'astn',}
#            'genre':'asgn','enc':'asfm','bitrate':'asbr'}

        for tr in self.tracks:
            if tr is not None:
                #http://<server>:<port>/databases/<dbid>/items/<id>.<type>?session-id=<sessionid>
                
                uri = "http://%s:%s/databases/%s/items/%s.%s?session-id=%s" % \
                    (self.server, self.port, self.database.id, tr.id,
                    tr.type, self.session.sessionid)

                temp = track.Track(uri)
                

                for field in eqiv.keys():
                    try:
                        temp.tags[field] = [u'%s'%tr.atom.getAtom(eqiv[field])]
                        if temp.tags[field] == "None":
                            temp.tags[field] = ["Unknown"]
                    except:
                        temp.tags[field] = ["Unknown"]

                
                #TODO: convert year (asyr) here as well, what's the formula?
                try:
                    temp.tags["__length"] = tr.atom.getAtom('astm') / 1000
#                    temp.tags["__length"] = tr.time / 1000
                except:
                    temp.tags["__length"] = 0

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


class DAAPLibrary(collection.Library):
    def __init__(self, daap_share, col=None):
#        location = "http://%s:%s/databasese/%s/items/" % (daap_share.server, daap_share.port, daap_share.database.id)
        location = "http://%s:%s/" % (daap_share.server, daap_share.port)
        collection.Library.__init__(self, location)
        self.daap_share = daap_share
        self.collection = collection

#    @common.threaded        
    def rescan(self, notify_interval=None):
    
        if self.collection is None:
            return True
            
        if self.scanning:
            return
            
        logger.info('Scanning library: %s' % self.active_share.name)
        self.scanning = True
        db = self.collection
        
        self.active_share.reload()
        print 'post rel'
        if self.active_share.all:
            count = len(self.active_share.all)
        else:
            count = 0
            
       
        if count > 0:
            self.collection.add_tracks(self.active_share.all)
        
        
        if notify_interval is not None:
            event.log_event('tracks_scanned', self, count)
            
        # track removal?
        
    def _count_files(self):
        count = 0
        if self.active_share:
            count = len(self.active_share.all)
            
        return count


class NetworkPanel(CollectionPanel):
    """
        A panel that displays the available DAAP shares and their contents.
    """
    def __init__(self, parent, daap_share):
        """
            Expects a parent gtk.Window, and a daap connection.
        """
        
        self.name = daap_share.name
        self.daap_share = daap_share
        self.net_collection = collection.Collection(self.name)
#        self.net_collection.add_library(library)
        CollectionPanel.__init__(self, parent, self.net_collection, self.name, _show_collection_empty_message=False)

        self.all = []

        self.connect_id = None
        
        #menu_item = gtk.MenuItem(_("Disconnect"))
#        menu_item.connect('activate', lambda x: disconnect_share(library.active_share))
#        menu_item.show()
        self.menu.append(_("Disconnect"), lambda x, y: disconnect_share(daap_share))


    @common.threaded
    def refresh(self):
        self.daap_share.reload()
            
        if self.daap_share.all:
            count = len(self.daap_share.all)
        else:
            count = 0
        
        if count > 0:
#            gobject.idle_add(self.collection.add_tracks, self.daap_share.all)
            self.collection.add_tracks(self.daap_share.all)
            gobject.idle_add(self.load_tree)
        


    def save_selected(self, widget=None, event=None):
        """
            Save the selected tracks to disk.
        """
        items = self.get_selected_items()
        dialog = gtk.FileChooserDialog(_("Select a save location"),
            APP.window, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            (_('Open'), gtk.RESPONSE_OK, _('Cancel'), gtk.RESPONSE_CANCEL))
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
    if exaile.loading:
        event.add_callback(__enb, 'gui_loaded')
    else:
        __enb(None, exaile, None)
        
def __enb(eventname, exaile, wat):
    gobject.idle_add(_enable, exaile)
    
def _enable(exaile):
    global MENU_ITEM
    
    if not DAAP:
        raise Exception("DAAP could not be imported.")

#    if not AVAHI:
#        raise Exception("AVAHI could not be imported.")
        
    tools = exaile.gui.builder.get_object('tools_menu')
    MENU_ITEM = gtk.MenuItem(_('Connect to DAAP...'))
    
    menu = guiutil.Menu()
    menu_item = gtk.MenuItem(_('Manually...'))
    menu_item.connect('activate', manual_connect, exaile)
    menu.append_item(menu_item)

    MENU_ITEM.set_submenu(menu)
    tools.append(MENU_ITEM)
    MENU_ITEM.show_all()
    
    if AVAHI:
        AVAHI_INTERFACE = DaapAvahiInterface(exaile, menu)
    else:
        logger.warn('AVAHI could not be imported, you will not see broadcast shares.')

def teardown(exaile):
    for x in PANELS:
        disconnect_share(PANELS[x].library.active_share)
           

def disable(exaile):
    global MENU_ITEM, PANELS
    
    # disconnect from active shares
    for x in PANELS:
        disconnect_share(PANELS[x].library.active_share)
        
    
    if MENU_ITEM:
        MENU_ITEM.hide()
        MENU_ITEM.destroy()
        MENU_ITEM = None


    event.remove_callback(__enb, 'gui_loaded')


# vi: et ts=4 sts=4 sw=4
