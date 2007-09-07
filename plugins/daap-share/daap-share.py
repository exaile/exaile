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

import os, gtk, dbus
import xl.plugins as plugins
from xl import panels, media, xlmisc, library, common
from gettext import gettext as _
from xl.panels import collection
import xl.path

try:
    import daap
    from daap import DAAPClient
    DAAP = True
except:
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
except:
    AVAHI = False

PLUGIN_NAME = _("Music Sharing")
PLUGIN_AUTHORS = ['Aren Olson <reacocard@gmail.com>']
PLUGIN_VERSION = '0.7.7'
PLUGIN_DESCRIPTION = _(r"""Allows playing of DAAP music shares.
\n\nDepends: python-daap, python-avahi.""")

PLUGIN_ENABLED = False
PLUGIN_ICON = gtk.Button().render_icon('gtk-network', gtk.ICON_SIZE_MENU)

APP = None
SETTINGS = None
TAB_PANE = None
PANEL = None
AVAHI_INTERFACE = None
CONNECTIONS = {}

# Have to use a string since we only have one file.
GLADE_XML_STRING = None

def load_data(zip):
    """
        Called by Exaile to load the data from the zipfile
    """
    global GLADE_XML_STRING

    GLADE_XML_STRING = zip.get_data('gui.glade')

class DaapAvahiInterface: #derived from python-daap/examples
    """
        Handles detection of DAAP shares via Avahi.
    """

    def new_service(self, interface, protocol, name, type, domain, flags):
        interface, protocol, name, type, domain, host, aprotocol, address, port, txt, flags = self.server.ResolveService(interface, protocol, name, type, domain, avahi.PROTO_UNSPEC, dbus.UInt32(0))
        """
            Called when a new share is found.
        """
#        print "DAAP: Found %s." % name
        #Use all available info in key to avoid name conflicts.
        nstr = '%s%s%s%s%s' % (interface, protocol, name, type, domain)
        CONNECTIONS[nstr] = DaapConnection(name, address, port)
        self.panel.update_connections()

    def remove_service(self, interface, protocol, name, type, domain, flags):
        """
            Called when the connection to a share is lost.
        """
#        print "DAAP: Lost %s." % name
        nstr = '%s%s%s%s%s' % (interface, protocol, name, type, domain)
        del CONNECTIONS[nstr]
        self.panel.update_connections()

    def __init__(self, panel):
        """
            Sets up the avahi listener.
        """
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
        self.panel = panel

class DaapConnection(object):
    """
        A connection to a DAAP share.
    """
    def __init__(self, name, server, port):
        self.all = library.TrackData()
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
        except daap.DAAPError:
            self.auth = True
            self.connected = False
            raise daap.DAAPError

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
        self.all = library.TrackData()
        self.connected = False

    def reload(self):
        """
            Reload the tracks from the server
        """
        APP.status.set_first(_("Retrieving track list from server..."))
        self.tracks = None
        self.database = None
        self.all = library.TrackData()
        self.get_database()
        self.convert_list()
        APP.status.clear()


    def get_database(self):
        """
            Get a DAAP database and its track list.
        """
        if self.session:
            self.database = self.session.library()
            self.get_tracks(1)

    def get_tracks(self, reset = 0):
        """
            Get the track list from a DAAP database
        """
        if reset or self.tracks == None:
            self.tracks = self.database.tracks()
            return self.tracks

    def convert_list(self):
        """
            Converts the DAAP track database into DaapTracks.
        """
        i = 0
        while i < len(self.tracks):
            tr = self.tracks[i]
            if tr:
                temp = media.Track()
                # Convert DAAPTrack's attributes to media.Track's.
                eqiv = {'title':'minm','artist':'asar','album':'asal',
                    'genre':'asgn','track':'astn','enc':'asfm',
                    'bitrate':'asbr'}
                for field in eqiv.keys():
                    try:
                        setattr(temp, field, u'%s'%tr.atom.getAtom(eqiv[field]))
                        if getattr(temp, field) == "None":
                            setattr(temp, field, "Unknown")
                    except:
                        setattr(temp, field, "Unknown")

                #TODO: convert year (asyr) here as well, what's the formula?
                try:
                    setattr(temp, '_len', tr.atom.getAtom('astm') / 1000)
                except:
                    setattr(temp, '_len', 0)
                temp.type = getattr(tr, 'type')
                temp.daapid = getattr(tr, 'id')
                temp.connection = self
    #http://<server>:<port>/databases/<dbid>/items/<id>.<type>?session-id=<sessionid>
                temp.loc = "http://%s:%s/databases/%s/items/%s.%s?session-id=%s" % \
                    (self.server, self.port, self.database.id, temp.daapid,
                    temp.type, self.session.sessionid)
                temp._rating = 2 #bad, but it works.
                self.all.append(temp)
            i = i + 1

        APP.plugin_tracks[plugins.name(__file__)] = self.all

    #@common.threaded
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




class NetworkPanel(collection.CollectionPanel):
    """
        A panel that displays the available DAAP shares and their contents.
    """
    name = 'network'
    def __init__(self, exaile, xml):
        """
            Expects the main exaile object, and a glade xml object.
        """
        self.xml = xml
        self.exaile = exaile

        self.db = exaile.db
        self.connected = False
        self.all = {}

        self.connection_list = []

        self.transfer_queue = None
        self.transferring = False
        self.queue = None

        self.keyword = None
        self.track_cache = dict()
        self.start_count = 0
        self.tree = None
        self.connect_id = None
        self.separator_image = self.exaile.window.render_icon('gtk-remove', 
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.artist_image = gtk.gdk.pixbuf_new_from_file(
            xl.path.get_data('images', 'artist.png')
        self.album_image = self.exaile.window.render_icon('gtk-cdrom',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.track_image = gtk.gdk.pixbuf_new_from_file(
            xl.path.get_data('images', 'track.png')
        self.genre_image = gtk.gdk.pixbuf_new_from_file(
            xl.path.get_data('images', 'genre.png')

        self.setup_widgets()

        self.xml.get_widget('shares_combo_box').connect('changed',
            self.switch_share)

    def switch_share(self, widget=None):
        """
            Change the active share
        """
        shares_box = self.xml.get_widget('shares_combo_box')
        if shares_box.get_active() != -1:
            if shares_box.get_active_text() == _('Custom location...'):
                while 1:
                    dialog = common.TextEntryDialog(self.exaile.window,
                        _("Enter IP address and port for share"),
                        _("Enter IP address and port."))
                    resp = dialog.run()
                    if resp == gtk.RESPONSE_OK:
                        loc = dialog.get_value()
                        address = loc.split(':')[0]
                        try:
                            port = loc.split(':')[1]
                        except IndexError:
                            dialog = gtk.MessageDialog(APP.window,
                            gtk.DIALOG_MODAL, gtk.MESSAGE_INFO, gtk.BUTTONS_OK,
                            _("""You must supply an IP address and port number, in the format
<ip address>:<port>"""))
                            dialog.run()
                            dialog.destroy()
                            continue
                        self.active_share = DaapConnection("Custom: ", address, port)
                        break
                    elif resp == gtk.RESPONSE_CANCEL:
                        shares_box.set_active(-1)
                        self.active_share = None
                        break
            else:
                self.active_share = self.connection_list[shares_box.get_active()]

            if self.active_share:
                if not self.active_share.connected:
                    try:
                        self.active_share.connect()
                    except daap.DAAPError:
                        while 1:
                            dialog = common.TextEntryDialog(self.exaile.window,
                                _("%s %s") % ("Enter password for",
                                 self.active_share.name ),
                                _("Password required."))
                            dialog.entry.set_visibility(False)
                            resp = dialog.run()
                            if resp == gtk.RESPONSE_OK:
                                password = dialog.get_value()
                                try:
                                    self.active_share.connect(password)
                                    break
                                except daap.DAAPError:
                                    continue
                            elif resp == gtk.RESPONSE_CANCEL:
                                shares_box.set_active(-1)
                                self.active_share = None
                                break
                    except:
                        dialog = gtk.MessageDialog(APP.window,
                            gtk.DIALOG_MODAL, gtk.MESSAGE_INFO, gtk.BUTTONS_OK,
                            _("Could not connect to server. Did you enter the correct address and port?"))
                        result = dialog.run()
                        dialog.destroy()
                        print result
                        shares_box.set_active(-1)
                        self.active_share = None

                if self.active_share and self.active_share.all:
                    self.all = self.active_share.all
                else:
                    self.all = {}
            else:
                self.all = {}
        else:
            self.all = {}
        self.load_tree(1)

    def search_tracks(self, keyword, all):
        """
            Search the tracks for keyword.
        """
        if keyword:
            check = []
            for track in self.all:
                for item in ('artist', 'album', 'title'):
                    attr = getattr(track, item)
                    if attr.lower().find(keyword.lower()) > -1:
                        check.append(track)
                        break
        else:
            check = self.all

        def stripit(field):
            return library.lstrip_special(library.the_cutter(field))

        slstrip = library.lstrip_special

        if self.choice.get_active() == 2:
            n = 5
            new = [(slstrip(a.genre), stripit(a.artist), slstrip(a.album),
                    a.track, slstrip(a.title), a) for a in check]
        elif self.choice.get_active() == 0:
            n = 4
            new = [(stripit(a.artist), slstrip(a.album), a.track, 
                    slstrip(a.title), a) for a in check]
        elif self.choice.get_active() == 1:
            n = 3
            new = [(slstrip(a.album), a.track, 
                    slstrip(a.title), a ) for a in check]

        new.sort()
        return library.TrackData([a[n] for a in new])

    def update_connections(self):
        sbox = self.xml.get_widget('shares_combo_box')
        n = 0
        while n < 100: #not good, how can we find the # of entries?
            sbox.remove_text(0) #No exception when nothing to remove?!
            n = n + 1
        self.connection_list = []
        for c in CONNECTIONS.values():
            self.connection_list.append(c)
        for c in self.connection_list:
            sbox.append_text('%s (%s:%s)' % (c.name, c.server, c.port))
        sbox.append_text(_('Custom location...'))

    def create_popup(self):
        """
            Creates the context menu.
        """
        menu = xlmisc.Menu()
        self.append = menu.append(_("Append to Current"),
            self.append_to_playlist)

        self.queue_item = menu.append(_("Queue Items"),
            self.append_to_playlist)
        menu.append_separator()

        self.save_item = menu.append(_("Save Items"),
            self.save_selected)

        self.menu = menu

    @common.threaded
    def load_tree(self, event=None):
        if event and not isinstance(event, gtk.ComboBox):
            shares_box = self.xml.get_widget('shares_combo_box')
            if shares_box.get_active() != -1:
                #active_share = self.connection_list[shares_box.get_active()]
                self.active_share.reload()
                if self.active_share.all:
                    self.all = self.active_share.all
                else:
                    self.all = {}
        collection.CollectionPanel.load_tree(self, event)

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

def initialize():
    """
        Adds 'Network' tab to side panel, sets up Avahi.
    """
    global APP, TAB_PANE, GLADE_XML_STRING, PANEL, CONNECTIONS

    if not DAAP:
        raise plugins.PluginInitException("python-daap is not available, "
                    "disabling Music Sharing plugin.")
        return False

    if not AVAHI:
        raise plugins.PluginInitException("Avahi is not available, "
                    "disabling Music Sharing plugin.")
        return False

    xml = gtk.glade.xml_new_from_buffer(GLADE_XML_STRING,
        len(GLADE_XML_STRING))

    TAB_PANE = xml.get_widget('network_box')
    PANEL = NetworkPanel(APP, xml)
    AVAHI_INTERFACE = DaapAvahiInterface(PANEL)

    notebook = APP.xml.get_widget('side_notebook')
    tab_label = gtk.Label()
    tab_label.set_text(_('Network'))
    tab_label.set_angle(90)
    notebook.append_page(TAB_PANE, tab_label)

    TAB_PANE.show_all()
    PANEL.load_tree()
    PANEL.update_connections()

    return True


def destroy():
    """
        Removes 'Network' tab, disconnects from shares.
    """
    global CONNECTIONS
    TAB_PANE.destroy()
    AVAHI_INTERFACE = None
    for s in CONNECTIONS.values():
        #disconnect required for servers that limit connections, eg. itunes.
        s.disconnect()
#        print "DAAP: Disconnected from %s." % s.name
    CONNECTIONS = {}
    PANEL = None
    if APP.plugin_tracks.has_key(plugins.name(__file__)):
        del APP.plugin_tracks[plugins.name(__file__)]
