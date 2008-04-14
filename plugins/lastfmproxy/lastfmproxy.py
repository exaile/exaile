# Copyright (C) 2006 Adam Olsen 
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

import os, zipfile, md5, random, time, re, sys
import xl.plugins as plugins
from gettext import gettext as _
random.seed(time.time())
from xl import common, xlmisc
from xl.panels import radio
import xl.media as media
import time, gtk, gobject

PLUGIN_NAME = _("LastFM Radio")
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = "0.1"
PLUGIN_DESCRIPTION = _(r"""Allows for streaming via lastfm proxy.\n\n
This plugin is very beta and still doesn't work perfectly.  If you find\n
you can't change stations, hit "stop", wait 10 seconds, and then try.
""")
PLUGIN_ENABLE = False
PLUGIN_ICON = None

TMP_DIR = None
PROXY = None
PLUGIN = None
HTTP_CLIENT = None
MENU_ITEM = None

def lastfm_error(message):
    common.error(APP.window, message)

class LastFMTrack(media.Track):
    def __init__(self, *args):
        media.Track.__init__(self, *args)
        self.type = 'stream'
        self.proxy = PROXY
        self.lfmstation = None

    @common.threaded
    def start_play(self):
        if not self.proxy.proxy_ready:
            gobject.idle_add(lastfm_error, _("The LastFM server has not reported that "
                "it's ready yet.  Please wait a moment."))
            
            return
        time.sleep(.5)
        HTTP_CLIENT.req('/' + self.lfmstation) 

class LastFMDriver(radio.RadioDriver):
    def __init__(self, panel):
        self.model = panel.model
        self.folder_icon = panel.folder
        self.note = panel.track
        self.tree = panel.tree
        self.panel = panel
        self.exaile = APP
        self.last_node = None

        self.custom_urls = self.exaile.settings.get_list('custom_urls',
            plugin=plugins.name(__file__))

    def command(self, command):
        self.lfmcommand = command
        self.do_command()

    @common.threaded
    def do_command(self):
        HTTP_CLIENT.req(self.lfmcommand)

    def get_menu(self, item, menu):
        menu.append(_("Add Station"), self.on_add, 'gtk-add')
        if isinstance(item, radio.RadioGenre) and item.custom:
            menu.append(_("Remove Station"), self.on_remove, 'gtk-delete')
            self.last_menu_item = item
        return menu

    def on_add(self, *e):
        """
            Called when the user wants to add a station
        """
        dialog = common.MultiTextEntryDialog(APP.window, _("Add Station"))
        dialog.add_field(_("Name"))
        dialog.add_field(_("URL"))

        result = dialog.run()
        values = dialog.get_values()
        dialog.hide()
        if result == gtk.RESPONSE_OK:
            if values[1].find("://") == -1:
                values[1] = "lastfm://%s" % values[1]
            self.custom_urls.append(values)
            self.exaile.settings.set_list('custom_urls',
                self.custom_urls, plugin=plugins.name(__file__))

            item = radio.RadioGenre(values[0], self)
            item.lastfm_url = values[1]
            item.custom = True
            node = self.model.append(self.last_node, [self.note, item])
            item.node = node

    def on_remove(self, *e):
        item = self.last_menu_item
        node = item.node

        result = common.yes_no_dialog(APP.window, _("Are you sure you "
            "want to remove this item?"))
        if result == gtk.RESPONSE_YES:
            self.model.remove(node)
            
            new_custom = []
            for station, url in self.custom_urls:
                if item.name == station and item.lastfm_url == url:
                    continue
                else:
                    new_custom.append([station, url])

            self.custom_urls = new_custom
            self.exaile.settings.set_list('custom_urls',
                self.custom_urls, plugin=plugins.name(__file__))

        return False

    def load_streams(self, node, load_node, use_cache=True):
        stations = (
            ('Personal', 'lastfm://user/synic/personal'),
            ('Recommended', 'lastfm://user/synic/recommended/100'),
            ('Neighbourhood', 'lastfm://user/synic/neighbours'),
            ('Loved Tracks', 'lastfm://user/synic/loved'),
        )

        for station, url in stations:
            item = radio.RadioGenre(station, self)
            item.lastfm_url = url
            item.custom = False
            n = self.model.append(node, [self.note, item])
            item.node = n

        # custom
        for station, url in self.custom_urls:
            item = radio.RadioGenre(station, self)
            item.lastfm_url = url
            item.custom = True
            n = self.model.append(node, [self.note, item])
            item.node = n

        self.model.remove(load_node)
        self.last_node = node

    def load_genre(self, genre, rel=False):
        tr = LastFMTrack()
        tr.loc = 'http://localhost:1881/lastfm.mp3'
        tr.artist = 'LastFM Radio!'
        tr.album = "LastFM: %s" % str(genre)
        tr.title = "LastFM: %s" % str(genre)
        tr.lfmstation = genre.lastfm_url

        self.exaile.tracks.append_song(tr)
        self.exaile.player.play_track(tr)
        
    def __str__(self):
        return "LastFM Radio"

def unzip_file(file, odir):
    """
        Unzips "file" to "odir" (output directory)
    """
    z = zipfile.ZipFile(file)
    for name in z.namelist():
        m = re.match(r'^(.*)/([^/]*)$', name)
        if m:
            dir = m.group(1)

            if not os.path.isdir(os.path.join(odir, dir)):
                os.makedirs(os.path.join(odir, dir))

            if not m.group(2): continue

        h = open(os.path.join(odir, name), 'w')
        h.write(z.read(name))
        h.close()

def load_data(zip):
    """
        Loads the data from the zipfile
    """
    global TMP_DIR
    if TMP_DIR: return

    fname = "/tmp/lfmfile%s" % md5.new(str(random.randrange(0,
        234234234234324))).hexdigest()
    TMP_DIR = "/tmp/lfmdir%s" % md5.new(str(random.randrange(0,
        123471287348834))).hexdigest()

    os.mkdir(TMP_DIR)
    h = open(fname, 'w')
    h.write(zip.get_data("data/lastfmproxy.zip"))
    h.close()

    unzip_file(fname, TMP_DIR)

@common.threaded
def run_proxy(config):
    PROXY.run(config.bind_address, config.listenport)

def initialize():
    global PROXY, PLUGIN, HTTP_CLIENT, MENU_ITEM
    sys.path.append(TMP_DIR)

    import lastfmmain
    import config
    import httpclient

    settings = APP.settings


    port = settings.get_int('listenport', plugin=plugins.name(__file__),
        default=1881)
    config.listenport = port
    config.username = settings.get_str('lastfmuser',
        plugin=plugins.name(__file__),
        default=settings.get_str('lastfm/user', ''))
    config.password = settings.get_crypted('lastfmpass',
        plugin=plugins.name(__file__),
        default=settings.get_str('lastfm/pass', ''))


    PROXY = lastfmmain.proxy(config.username, config.password)
    PROXY.basedir = TMP_DIR
    run_proxy(config)

    PLUGIN = LastFMDriver(APP.pradio_panel)
    APP.pradio_panel.add_driver(PLUGIN, plugins.name(__file__))
    HTTP_CLIENT = httpclient.httpclient('localhost', config.listenport)

    MENU_ITEM = xlmisc.Menu()
    MENU_ITEM.append(_("Skip"), lambda *e: PLUGIN.command('/skip'))
    MENU_ITEM.append(_("Love"), lambda *e: PLUGIN.command('/love'))
    MENU_ITEM.append(_("Ban"), lambda *e: PLUGIN.command('/ban'))
    
    APP.plugins_menu.append_menu(_("LastFM"), MENU_ITEM)
    
    return True

def destroy():
    global PLUGIN, MENU_ITEM
    if TMP_DIR:
        sys.path.remove(TMP_DIR) 

    if PLUGIN:
        APP.pradio_panel.remove_driver(PLUGIN)

    if MENU_ITEM:
        MENU_ITEM.hide()
        MENU_ITEM.destroy()

    MENU_ITEM = None
    PLUGIN = None
