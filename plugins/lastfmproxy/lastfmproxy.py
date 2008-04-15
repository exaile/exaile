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
import time, gtk, gobject, gtk.glade

PLUGIN_NAME = _("LastFM Radio")
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = "0.1.3"
PLUGIN_DESCRIPTION = _(r"""Allows for streaming via lastfm proxy.\n\nThis
plugin is very beta and still doesn't work perfectly.""")
PLUGIN_ENABLED = False
PLUGIN_ICON = None

TMP_DIR = None
PROXY = None
PLUGIN = None
HTTP_CLIENT = None
BUTTONS = []
TIPS = gtk.Tooltips()
GLADE_XML_STRING = None

def lastfm_error(message):
    common.error(APP.window, message)

class LastFMDriver(radio.RadioDriver):
    def __init__(self, panel):
        self.model = panel.model
        self.folder_icon = panel.folder
        self.note = panel.track
        self.tree = panel.tree
        self.panel = panel
        self.exaile = APP
        self.last_node = None
        self.no_new_page = True

        self.custom_urls = self.exaile.settings.get_list('custom_urls',
            plugin=plugins.name(__file__))

    def command(self, command):
        self.lfmcommand = command
        self.exaile.status.set_first(_("Running command: %s...") %
            command, 3500) 
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
        current = self.exaile.player.current
        if hasattr(current, 'lastfm_track'):
            current.album = "LastFM: %s" % str(genre)
            self.exaile.tracks.refresh_row(current)

            self.command("/changestation/%s" % genre.lastfm_url)
            self.exaile.status.set_first(_("Changing stations..."), 3500)
            if not current in self.exaile.tracks.songs:
                self.exaile.tracks.append_song(current)
            return
        tr = media.Track()
        tr.type = 'stream'
        tr.loc = 'http://localhost:1881/lastfm.mp3'
        tr.artist = 'LastFM Radio!'
        tr.album = "LastFM: %s" % str(genre)
        tr.title = "LastFM: %s" % str(genre)
        tr.lastfm_track = True

        self.exaile.tracks.append_song(tr)
        self.exaile.player.play_track(tr)
        self.command('/changestation/%s' % genre.lastfm_url)
        
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
    global TMP_DIR, PLUGIN_ICON, GLADE_XML_STRING
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

    GLADE_XML_STRING = zip.get_data('data/lastfmproxy.glade')

@common.threaded
def run_proxy(config):
    PROXY.run(config.bind_address, config.listenport)

BUTTON_ITEMS = (
    ('LastFM: Skip this track', 'gtk-media-forward', '/skip'),
    ('LastFM: Mark this track as loved', 'gtk-add', '/love'),
    ('LastFM: Ban this track', 'gtk-delete', '/ban'),
)

def initialize():
    global PROXY, PLUGIN, HTTP_CLIENT, BUTTONS
    if not TMP_DIR in sys.path: sys.path.append(TMP_DIR)

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

    if not BUTTONS:
        for tooltip, icon, command in BUTTON_ITEMS:
            button = gtk.Button()
            button.connect('clicked', lambda w, command=command: PLUGIN.command(command))
            image = gtk.Image()
            image.set_from_stock(icon, gtk.ICON_SIZE_MENU)
            button.set_size_request(32, 32)
            button.set_image(image)
            TIPS.set_tip(button, tooltip)
            APP.xml.get_widget('rating_toolbar').pack_start(button)
            BUTTONS.append(button)
        for button in BUTTONS:
            button.show()

    return True

def destroy():
    global PLUGIN, MENU_ITEM, PROXY, BUTTONS
    if TMP_DIR:
        sys.path.remove(TMP_DIR) 

    if PLUGIN:
        APP.pradio_panel.remove_driver(PLUGIN)

    if BUTTONS:
        for button in BUTTONS:
            button.hide()
            button.destroy()

        BUTTONS = []
    
    if PROXY:
        PROXY.quit = True

    PROXY = None
    MENU_ITEM = None
    PLUGIN = None

def use_main_toggled(box, user, password):
    active = not box.get_active()
    user.set_sensitive(active)
    password.set_sensitive(active)

def quick_init():
    """
        Runs initialize, but returns False so the timer doesn't continue to
        run
    """
    global PROXY
    initialize()

    return False

def configure():
    global PROXY
    exaile = APP
    settings = exaile.settings

    xml = gtk.glade.xml_new_from_buffer(GLADE_XML_STRING,
        len(GLADE_XML_STRING))

    dialog = xml.get_widget('ConfigurationDialog')
    use_main = xml.get_widget('lastfm_use_main')
    lastfm_user = xml.get_widget('lastfm_user')
    lastfm_pass = xml.get_widget('lastfm_pass')
    lastfm_listen_port = xml.get_widget('lastfm_listen_port')

    use_main.set_active(settings.get_boolean('use_main',
        plugin=plugins.name(__file__), default=True))

    lastfm_user.set_text(settings.get_str('lastfmuser',
        plugin=plugins.name(__file__),
        default=settings.get_str('lastfm/user', '')))
    lastfm_pass.set_text(settings.get_crypted('lastfmpass',
        plugin=plugins.name(__file__),
        default=settings.get_str('lastfm/pass', '')))

    lastfm_listen_port.set_text(settings.get_str('listenport',
        plugin=plugins.name(__file__), default=1881))

    use_main.connect('toggled', lambda *e: use_main_toggled(use_main,
        lastfm_user, lastfm_pass))
    use_main_toggled(use_main, lastfm_user, lastfm_pass)

    result = dialog.run()
    dialog.hide()
    if result == gtk.RESPONSE_OK:
        if PROXY: 
            PROXY.quit = True
            exaile.player.stop()
        settings.set_boolean('use_main', use_main.get_active(),
            plugin=plugins.name(__file__))
        settings.set_str('lastfm_user', lastfm_user.get_text(), 
            plugin=plugins.name(__file__))
        settings.set_crypted('lastfm_pass', lastfm_pass.get_text(),
            plugin=plugins.name(__file__))

        settings.set_str('listenport', lastfm_listen_port.get_text(),
            plugin=plugins.name(__file__))

        if PLUGIN_ENABLED:
            gobject.timeout_add(5000, quick_init)

icon_data = ["16 16 72 1",
" 	c None",
".	c #D20039",
"+	c #D71B4E",
"@	c #EE9EB4",
"#	c #F9DFE6",
"$	c #FAE5EB",
"%	c #F5C8D4",
"&	c #E05077",
"*	c #E04D75",
"=	c #F6CAD6",
"-	c #F7D3DD",
";	c #E87A98",
">	c #D71E50",
",	c #F8D8E1",
"'	c #F5C5D2",
")	c #E1547A",
"!	c #DD416B",
"~	c #EB8DA6",
"{	c #FDF5F7",
"]	c #E36084",
"^	c #D40A41",
"/	c #FAE0E7",
"(	c #E66F8F",
"_	c #E04F76",
":	c #EC94AC",
"<	c #D40D43",
"[	c #EFA2B7",
"}	c #F3BBCA",
"|	c #E25C80",
"1	c #DD3D68",
"2	c #DC3965",
"3	c #F8DAE2",
"4	c #E1577D",
"5	c #D3033B",
"6	c #F6CBD7",
"7	c #EA8AA4",
"8	c #E67191",
"9	c #FBEAEF",
"0	c #F3BAC9",
"a	c #E36184",
"b	c #D3083F",
"c	c #F9DCE4",
"d	c #E05279",
"e	c #FAE1E8",
"f	c #D40E44",
"g	c #D82253",
"h	c #E9829E",
"i	c #FBEBEF",
"j	c #ED9BB1",
"k	c #F0A9BC",
"l	c #F1B1C2",
"m	c #DB3562",
"n	c #F6CED9",
"o	c #E56B8C",
"p	c #E1557B",
"q	c #F9DDE5",
"r	c #D92657",
"s	c #FBE6EC",
"t	c #F2B4C5",
"u	c #DC3A66",
"v	c #D92959",
"w	c #E77997",
"x	c #FDF2F5",
"y	c #E15379",
"z	c #FBE8ED",
"A	c #DF4B73",
"B	c #DA2B5A",
"C	c #F2B8C8",
"D	c #D92A5A",
"E	c #FAE3E9",
"F	c #F7CFDA",
"G	c #E9839F",
" .............. ",
"................",
"................",
"................",
"..+@#$%&..*=-;..",
".>,')!~{]^/(_:<.",
".[}....|$1$2....",
".34....567890ab.",
".cd.....]efghij.",
".kl....mgno..pq.",
".rstuvwx2yzAB0C.",
"..Dl/EFa..G3clg.",
"................",
"................",
"................",
" .............. "]
PLUGIN_ICON = gtk.gdk.pixbuf_new_from_xpm_data(icon_data)
