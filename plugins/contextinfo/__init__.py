
from xl import main as ex, trax, common, event, xdg, settings, providers
from xl import player
from xl.trax import search, util
from xl.nls import gettext as _
from xlgui import panel
from xlgui.panel import menus
from xlgui.widgets.notebook import NotebookPage
from xlgui.widgets.common import DragTreeView
import HTMLParser
from StringIO import StringIO
try:
    from PIL import Image
except ImportError:
    import Image
import base64
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
import os
from xl.externals import pylast
import contextprefs
import re
import urllib
from gi.repository import WebKit2
import xlgui
from inspector import Inspector

# Last.fm API Key for Exaile
# if you reuse this code in a different application, please
# register your own key with last.fm
LFM_API_KEY = "3599c79a97fd61ce518b75922688bc38"

PANEL = None
CURPATH = os.path.realpath(__file__)
BASEDIR = os.path.dirname(CURPATH)+os.path.sep


class BrowserPage(WebKit2.WebView, providers.ProviderHandler):

    refresh_script = '''document.getElementById("%s").innerHTML="%s";onPageRefresh("%s");''';
    history_length = 6

    def __init__(self, builder, theme):
        WebKit2.WebView.__init__(self)
        providers.ProviderHandler.__init__(self, "context_page")

        # HACK: so that the panel menu works
        self.tree = self
        
        self.connect_events()
        self.hover = ''
        self.theme = theme
        self.loaded = False

        self.currentpage = None
        self.nowplaying = None

        self.history = []
        self.history_index = 0

        self.builder = builder
        self.setup_dnd()
        self.setup_buttons()

        self.drag_source_set(
                    Gdk.ModifierType.BUTTON1_MASK, self.targets,
                    Gdk.DragAction.COPY|Gdk.DragAction.MOVE)
        self.drag_source_set_icon_stock(Gtk.STOCK_DND)

        event.add_callback(self.on_playback_start, 'playback_track_start',
            player.PLAYER)
        event.add_callback(self.on_playback_end, 'playback_track_end',
            player.PLAYER)

        self.get_settings().set_property('enable-developer-extras', True)

        #FIXME: HACK! ajust zoom level for the new webkit version
        try:
            self.get_settings().get_property("enable-developer-extras")
            self.set_zoom_level(0.8)
        except:
            pass

        GLib.idle_add(self.on_home_clicked)

        # javascript debugger
        inspector = Inspector(self.get_web_inspector())

    def on_playback_start(self, obj=None, player=None, track=None):
        self.set_playing(track)

    def set_playing(self, track):
        self.lyrics_button.set_sensitive(True)
        self.nowplaying = PlayingPage(self.theme, track)
        self.push(self.nowplaying)

    def on_playback_end(self, obj=None, player=None, track=None):
        self.nowplaying = None
        self.lyrics_button.set_sensitive(False)

    def setup_buttons(self):
        self.prev_button = self.builder.get_object('PrevButton')
        self.prev_button.set_tooltip_text('Previous')
        self.prev_button.set_sensitive(False)
        self.prev_button.connect('clicked', self.on_prev_clicked)

        self.next_button = self.builder.get_object('NextButton')
        self.next_button.set_tooltip_text('Next')
        self.next_button.set_sensitive(False)
        self.next_button.connect('clicked', self.on_next_clicked)

        self.home_button = self.builder.get_object('HomeButton')
        self.home_button.set_tooltip_text('Home')
        self.home_button.connect('clicked', self.on_home_clicked)

        self.refresh_button = self.builder.get_object('RefreshButton')
        self.refresh_button.set_tooltip_text('Refresh')
        self.refresh_button.connect('clicked', self.on_refresh_page)
        self.refresh_button_image = self.builder.get_object('RefreshButtonImage')

        self.refresh_animation = GdkPixbuf.PixbufAnimation(BASEDIR+'loader.gif')

        self.lyrics_button = self.builder.get_object('LyricsButton')
        self.lyrics_button.set_tooltip_text('Lyrics')
        self.lyrics_button.set_sensitive(False)
        self.lyrics_button.connect('clicked', self.on_lyrics)

    def on_prev_clicked(self, widget=None,param=None):
        self.prev()

    def on_next_clicked(self, widget=None,param=None):
        self.next()

    def on_lyrics(self, widget=None,param=None):
        current_track = player.PLAYER.current
        if current_track is not None:
            self.push(LyricsPage(self.theme, current_track))

    def on_refresh_page(self, widget=None,param=None):
        self.currentpage.reinit()
        self.load(self.currentpage)

    def on_home_clicked(self, widget=None,param=None):
        current_track = player.PLAYER.current
        if current_track is not None and self.currentpage != self.nowplaying:
            if self.nowplaying:
                self.push(self.nowplaying)
            else:
                self.set_playing(current_track)
        else:
            self.push(DefaultPage(self.theme))

    def on_page_loaded(self, type=None, obj=None, data=None):
        self.refresh_button.set_sensitive(True)
        self.refresh_button_image.set_from_stock(Gtk.STOCK_REFRESH, 1)

    def on_field_refresh(self, type=None, obj=None, data=None):
        '''
           This is frequently called on a different thread, should 
           always execute the script on the main thread. If not, 
           errors may occur
        '''
        script = self.refresh_script % (data[0], u'%s' % data[1].replace('"', '\\"').replace('\n', '\\\n'), data[0])
        GLib.idle_add(self.execute_script, script)

    def push(self, page):
        self.history = self.history[:self.history_index+1]
        self.history.append(page)
        if len(self.history)>1:
            self.prev_button.set_sensitive(True)
        self.next_button.set_sensitive(False)
        self.history = self.history[-self.history_length:]
        self.history_index = len(self.history)-1
        self.load(page)

    def prev(self):
        self.history_index -= 1
        self.load(self.history[self.history_index])
        self.next_button.set_sensitive(True)
        if self.history_index == 0:
            self.prev_button.set_sensitive(False)

    def next(self):
        self.history_index +=1
        self.load(self.history[self.history_index])
        self.prev_button.set_sensitive(True)
        if len(self.history) == self.history_index+1:
            self.next_button.set_sensitive(False)

    def load(self, page):
        if self.currentpage != page:
            event.remove_callback(self.on_field_refresh, 'field_refresh', self.currentpage)
            event.remove_callback(self.on_page_loaded, 'loading_finished', self.currentpage)
            event.add_callback(self.on_field_refresh, 'field_refresh', page)
            event.add_callback(self.on_page_loaded, 'loading_finished', page)
        self.currentpage = page
        self.refresh_button.set_sensitive(False)
        self.refresh_button_image.set_from_animation(self.refresh_animation)
        self.loaded = False
        self.load_string(self.currentpage.get_html(), "text/html", "utf-8", "file://%s" % self.theme.path)

    def setup_dnd(self):
        self.targets = [("text/uri-list", 0, 0)]

        self.dragging = False
        self.connect('drag_begin', self.drag_begin)
        self.connect('drag_end', self.drag_end)
        self.connect('button_release_event', self.button_release)
        self.connect('button_press_event', self.button_press)
        self.connect('drag_data_get', self.drag_get_data)

    def button_press(self, widget, event):
        if event.button==3:
            if self.hover:
                menus.TrackPanelMenu(self).popup(event)
                return True
            else:
                return True

    def button_release(self, button, event):
        if event.button != 1 or self.dragging:
            self.dragging = False
            return True

    def drag_end(self, list, context):
        self.dragging = False
        self.drag_dest_set(Gtk.DestDefaults.ALL, self.targets,
            Gdk.DragAction.COPY|Gdk.DragAction.MOVE)

    def drag_begin(self, w, context):
        if self.hover == None:
            self.drag_source_set_icon_stock(Gtk.STOCK_CANCEL)
            return True
        self.dragging = True

        context.drag_abort(Gtk.get_current_event_time())
        selection = self.get_selected_tracks()
        if len(selection)>1:
            self.drag_source_set_icon_stock(Gtk.STOCK_DND_MULTIPLE)
        elif len(selection)>0: self.drag_source_set_icon_stock(Gtk.STOCK_DND)
        return False
    
    def get_selection_empty(self):
        return self.hover.split('://')[0] in ['track', 'artist', 'album', 'tag']

    def get_selected_tracks(self):
        tmp = self.hover.split('://', 1)[1]
        if self.hover.split('://')[0]=='track':
            return [self.currentpage.tracks[int(self.hover.split('://', 1)[1])]]
        if self.hover.split('://')[0]=='artist':
            return [x.track for x in search.search_tracks_from_string(
                	ex.exaile().collection, ('artist=="%s"' % tmp),
                    keyword_tags=['album', 'tracknumber'])]
        if self.hover.split('://')[0]=='album':
    	    return [x.track for x in search.search_tracks_from_string(
                	ex.exaile().collection, ('artist=="%s"' % tmp),
                    keyword_tags=['tracknumber'])]
        if self.hover.split('://')[0]=='tag':
    	    return [x.track for x in search.search_tracks_from_string(
                	ex.exaile().collection, ('genre=="%s"' % tmp),
                    keyword_tags=['artist', 'album', 'tracknumber'])]
        return []

    def drag_get_data(self, w, context, selection, target_id, etime):
        tracks = self.get_selected_tracks()
        for track in tracks:
            DragTreeView.dragged_data[track.get_loc_for_io()] = track
        urls = util.get_uris_from_tracks(tracks)
        selection.set_uris(urls)

    def connect_events(self):
        self.connect('navigation-requested', self._navigation_requested_cb)
        self.connect('load-finished', self._loading_stop_cb)
        self.connect("hovering-over-link", self._hover_link_cb)
        self.connect("populate-popup", self._populate_popup)

    def _loading_stop_cb(self, view, frame):
        if self.currentpage:
            self.currentpage.fill_async_fields()

    def _hover_link_cb(self, view, title, url):
        if not self.dragging:
            if url:
                self.hover = self.un_url(url)
            else:
                self.hover = None

    def un_url(self, url):
        return '/'.join(urllib.unquote(urlsplit).decode('idna') for urlsplit in url.split('/'))

    def on_append_items(self):
        """
            Appends the selected tracks to the current playlist
        """
        selected = self.get_selected_tracks()
        pl = xlgui.get_controller().main.get_selected_page()
        if pl:
            pl.playlist.add_tracks(selected)

    def _navigation_requested_cb(self, view, frame, networkRequest):
        link = self.un_url(networkRequest.get_uri()).split('://', 1)
        self.currentpage.link_clicked(link)
        if link[0] == 'track':
            self.on_append_items()
            return True
        elif link[0] == 'artist':
            self.push(ArtistPage(self.theme,link[1]))
            return True
        elif link[0] == 'tag':
            self.push(TagPage(self.theme, link[1]))
        elif link[0] == 'load':
            self.refresh_button.set_sensitive(False)
            self.refresh_button_image.set_from_animation(self.refresh_animation)
            self.currentpage.async_update_field(link[1])
            return True
        elif link[0] == 'http':
            self.currentpage=None
            return False
        else:
            for page_provider in self.get_providers():
                if page_provider.base == link[0]:
                    self.push(page_provider(self.theme, link[1]))

        if link[0] in ('album', 'rate'): return True
        return False

    def _populate_popup(self, view, menu):
        type = self.hover.split('://')[0]
        if type == 'artist':
            showincolitem = Gtk.MenuItem.new_with_mnemonic("Show in collection")
            menu.append(showincolitem)
            showincolitem.connect('activate', self._show_artist)
            menu.show_all()
        else:
            menu.show_all()

    def _show_artist(self, widget):
        ex.exaile().gui.panels['collection'].filter.set_text('artist=%s' % self.hover.split('://')[1])
        ex.exaile().gui.panel_notebook.set_current_page(0)

class ContextTheme(object):

    LOCAL_COLORS = None

    def __init__(self, name):
        self.name = name
        self.path = BASEDIR+name+os.path.sep
        self.parse_css()

    def get_ressource_path(self, ressource):
        return self.path+ressource

    def get_css(self):
        return self.css

    def parse_css(self):
        cssfile = open(self.path+'style.css')
        self.css = cssfile.read()
        if ContextTheme.LOCAL_COLORS == None:
            ContextTheme.LOCAL_COLORS = self.get_local_colors()
        self.css = self.css % ContextTheme.LOCAL_COLORS

    def to_hex_color(self, color):
        return '#%x%x%x' % (color.red*255/65535, color.green*255/65535, color.blue*255/65535)

    def get_local_colors(self):
        n = ex.exaile().gui.panel_notebook
        n.realize()
        style=n.get_style()
        l=[Gtk.StateType.NORMAL,Gtk.StateType.ACTIVE,Gtk.StateType.PRELIGHT,Gtk.StateType.SELECTED,Gtk.StateType.INSENSITIVE]
        s=['normal', 'active', 'prelight', 'selected', 'insensitive']
        colors = {}
        for t in ['base', 'text', 'fg', 'bg']:
            for i, j in zip(l, s):
                colors["%s-%s" % (t,j)] = self.to_hex_color(getattr(style, t)[i])
        return colors

def get_artist_tracks(artist):
    return [x.track for x in search.search_tracks_from_string(
                ex.exaile().collection, 'artist=="%s"'%artist.lower().replace('"', ''))]

def album_in_collection(artist, album):
    return len([x.track for x in search.search_tracks_from_string(
                ex.exaile().collection, ('artist=="%s" album=="%s"' % (artist,
		        album)))])>0

def tag_in_collection(tag):
    return len([x.track for x in search.search_tracks_from_string(
                ex.exaile().collection, ('genre=="%s"' % tag))])>0

def artist_in_collection(artist):
    return len([x.track for x in search.search_tracks_from_string(
                ex.exaile().collection, ('artist=="%s"' % artist))])>0

def track_in_collection(artist, title):
    tracks = [x.track for x in search.search_tracks_from_string(
                ex.exaile().collection, ('artist=="%s" title=="%s"' % (artist, title)))]
    if len(tracks)>0:
        return tracks[0]
    else:
        return None

class ImageBuffer(object):
    def __init__(self):
        self.buffer = ""
    
    def write(self, str):
        self.buffer+=str
        
    def get_base64(self):
        return base64.b64encode(self.buffer)

def get_image_data(data, size):
    imbuff = ImageBuffer()
    try:
        im = Image.open(StringIO(data))
    except Exception:
        im = Image.open(xdg.get_data_path('images/nocover.png'))
    im = im.resize(size, Image.ANTIALIAS)
    im.save(imbuff, "PNG")
    return 'data:image/png;base64,%s' % imbuff.get_base64()

def get_track_cover(track):
    return ex.exaile().covers.get_cover(track, set_only=True, use_default=True)

def get_track_tag(track, tag, default):
    try:
        return track.get_tag_display(tag)
    except:
        return default

def get_top_tracks(field, limit):
    tracks = [x.track for x in search.search_tracks_from_string(
                ex.exaile().collection, '! %s==__null__' % field)]
    tracks = util.sort_tracks([field], tracks, True)
    return tracks[:limit]

def get_top_albums(field, limit):
    albums = [x.track for x in search.search_tracks_from_string(
                ex.exaile().collection, '! %s==__null__' % field)]
    albums = util.sort_tracks([field], albums, True)
    return albums[:limit]

def get_top_artists(field, limit):
    artists = [x.artist for x in search.search_tracks_from_string(
                ex.exaile().collection, '! %s==__null__' % field)]
    artists = util.sort_tracks([field], artists, True)
    return artists[:limit]

class ContextPage(object):

    def __init__(self, theme, base, template, async=[]):
        templatefile = open(theme.path+template)
        self.template = templatefile.read()
        self.theme = theme
        self.base = base
        self.async = async
        self.reinit()

    def reinit(self):
        self.html = None
        self.data = {}
        self.setup_icons()
        self.tracks = []
        self.async = [field[0] for field in self.get_template_fields() if field[0] in self.async]
        self.fill_fields()

    def link_clicked(self, link):
        pass

    def setup_icons(self):
        self['artist-ico'] = self.get_img_tag(ContextPage.ARTIST_ICO_PATH, True)
        self['album-ico'] = self.get_img_tag(ContextPage.ALBUM_ICO_PATH, True)
        self['search-ico'] = self.get_img_tag(ContextPage.SEARCH_ICO_PATH, True)
        self['track-ico'] = self.get_img_tag(ContextPage.TRACK_ICO_PATH, True)

    def __getitem__(self, field):
        if not self.data.has_key(field):
            self.update_field(field)
            if not self.data.has_key(field):
                self.data[field] = '!!UNKNOWN_FIELD: %s!!' % field.replace('-', '_')
        return self.data[field]

    def __setitem__(self, field, value):
        self.data[field] = value

    def get_template_fields(self):
        string_field = re.compile('%\((.*?)\)s')
        fields = []
        for m in string_field.finditer(self.template):
            fields.append(m.group(1).split(':'))
        return fields[1:]

    @common.threaded
    def async_update_field(self, field):
        field = field.split(':')
        self.update_field(field[0], *field[1:])
        event.log_event('loading_finished', self, None)

    def update_field(self, name, *params):
        try:
            self[name] = getattr(self, '_'+name.replace('-', '_'))(*params)
        except:
            self[name] = ''
        if name in [f[0] for f in self.get_template_fields()]:
            event.log_event('field_refresh', self, (name, self[name]))

    def fill_fields(self):
        for field in self.get_template_fields():
            if field[0] not in self.async:
                self.update_field(*field)

    @common.threaded
    def fill_async_fields(self):
        for field in self.get_template_fields():
            if field[0] in self.async and field[0] not in self.data.keys():
                self.update_field(*field)
        event.log_event('loading_finished', self, None)

    def format_template(self):
        temp = self.data.copy()
        reformat = {'style':self.theme.get_css().replace('%', '%%')}
        for field in self.get_template_fields():
            name = field[0]
            reformat[':'.join(field)] = '%%(%s)s' % name
            if temp.has_key(name):
                temp[name] = '<span id="%s">%s</span>' % (name, temp[name])
            else:
                temp[name] = '<span id="%s"></span>' % name
        self.html = (self.template % reformat % temp).encode('utf-8')

    def get_html(self):
        self.format_template()
        return self.html

    def get_img_tag(self, path, local):
        if local:
            path = 'file://%s' % path
        return '<img src="%s"/>' % path

    def get_artist_href(self, artist):
        return 'artist://%s' % artist

    def get_artist_anchor(self, artist):
        if artist_in_collection(artist):
            css_class = 'col-artist-link'
        else:
            css_class = 'artist-link'
        return '<a class="%s" href="%s">%s</a>' % (css_class, self.get_artist_href(artist), artist)

    def get_tag_href(self, tag):
        return "tag://%s" % tag

    def get_tag_anchor(self, tag):
        if tag_in_collection(tag):
            return '<a class="col" href="%s">%s</a>' % (self.get_tag_href(tag), tag)
        else:
            return '<a href="%s">%s</a>' % (self.get_tag_href(tag), tag)

    def get_album_href(self, album):
        return "album://%s" % album

    def get_album_anchor_from_artist_title(self, artist, album):
        href = self.get_album_href(album)
        if album_in_collection(artist, album):
            return '<a class="col" href="%s">%s by %s</a>' % (self.get_album_href(album), album, artist)
        else:
            return '<a href="album://%s">%s by %s</a>' % (self.get_album_href(album), album, artist)

    def get_rating_html(self, rating):
        html=''
        star = xdg.get_data_path("images", "star.png")
        bstar = xdg.get_data_path("images", "emptystar.png")
        maximum = settings.get_option("rating/maximum", 5)
        for i in range(rating):
            html+='<a href="rate://%d"><img src="file://%s"/></a>' % (i+1, star)
        for i in range(maximum-rating):
            html+='<a href="rate://%d"><img src="file://%s"/></a>' % (rating+i+1, bstar)
        return html

    def get_cds_html(self, tracks):
        list = []
        html = ''
        cd = ''
        for tr in tracks:
            if get_track_tag(tr, 'album', 'unknown').lower() != cd.lower():
                if cd != '':
                    html+='<tr><td colspan=3><hr noshade="noshade"/></td></tr></table>'
                html+='<table class="cd-table">'
                cd=get_track_tag(tr, 'album', 'unknown')
                if cd== 'unknown':
                    track_nbr = len([x.track for x in search.search_tracks_from_string(
                            ex.exaile().collection, 'album==__null__')])
                else:
                    track_nbr = len([x.track for x in search.search_tracks_from_string(
                            ex.exaile().collection, 'album=="%s"' % cd)])
                cover = get_track_cover(tr)
                cover_data = get_image_data(cover, (60, 60))
                
                html+='''<tr class="cd-tr">\
<td><a href="album://%s"><img class="cd-img" src="%s"/></a></td>\
<td class="cd-title-td"><a href="album://%s"><b>%s</b><br/>%s</a></td>\
<td class="cd-right-td">%s tracks</td>\
</tr><tr><td colspan=3><hr noshade="noshade"/></td></tr>''' % \
    (cd, cover_data, cd, cd, get_track_tag(tr, 'date', ''), track_nbr)

            anchor = self.get_track_anchor_from_track(tr, img=True)
            html+='''<tr class="cd-track-tr">\
<td colspan=3 class='tracktd'>%s</td>\
</tr>''' % anchor
        html+='</table>'
        return html

    def get_text_from_track(self, track):
        return '%s - %s' % (get_track_tag(track, 'artist', 'unknown'),get_track_tag(track, 'title', 'unknown'))

    def get_href_from_track(self, track):
        self.tracks.append(track)
        return 'track://%d' % int(len(self.tracks)-1)

    def get_track_anchor_from_track(self, track, img=True):
        css_class = ''
        try:
            if track == player.PLAYER.current:
                css_class = 'current'
        except: pass
        if img:
            img = self['track-ico']+' '
        else:
            img = ''
        text = self.get_text_from_track(track)
        href = self.get_href_from_track(track)
        return "<a class='track-link %s' href='%s'>%s%s</a>" % (css_class, href, img, text)

    def get_track_href_from_artist_title(self, artist, title):
        track = self.track_in_collection(artist, title)
        if track == None:
            return self.get_search_href(artist, title)
        else:
            return self.get_href_from_track(track)

    def get_track_anchor_from_artist_title(self, artist, title, img=True):
        track = self.track_in_collection(artist, title)
        if track == None:
            return self.get_search_anchor(artist, title)
        else:
            return self.get_track_anchor_from_track(track, img)

    def get_search_text(self, artist, title):
        return '%s - %s' % (artist, title)

    def get_search_href(self, artist, title):
        return 'search://%s//%s' % (artist, title)

    def get_search_anchor(self, artist, title, img=True):
        if img:
            img = self['search-ico']+' '
        else:
            img = ''
        href = self.get_search_href(artist, title)
        text = self.get_search_text(artist, title)
        return "<a class='search-link' href='%s'>%s%s</a>" % (href, img, text)

    def track_in_collection(self, artist, title):
        return track_in_collection(artist, title)
        
def __setup_context_page():
    '''Some of these icons may not exist'''
    
    ContextPage.TRACK_ICO_PATH = xdg.get_data_path('images/16x16/audio-x-generic.png')
    ContextPage.ARTIST_ICO_PATH = xdg.get_data_path("images/16x16/artist.png")
    
    ContextPage.SEARCH_ICO_PATH = None
    search_icon = Gtk.IconTheme.get_default().lookup_icon(Gtk.STOCK_FIND,
        Gtk.IconSize.SMALL_TOOLBAR, Gtk.IconLookupFlags.NO_SVG)
    if search_icon is not None:
        ContextPage.SEARCH_ICON_PATH = search_icon.get_filename()
        
    ContextPage.ALBUM_ICO_PATH = None
    album_icon = Gtk.IconTheme.get_default().lookup_icon(Gtk.STOCK_CDROM,
        Gtk.IconSize.SMALL_TOOLBAR, Gtk.IconLookupFlags.NO_SVG)
    if album_icon is not None:
        ContextPage.ALBUM_ICO_PATH = album_icon.get_filename()
    
__setup_context_page()
        

class DefaultPage(ContextPage):

    def __init__(self, theme, base='default://', template='default.html', async=[]):
        self.user = None
        try:
            self.username = settings.get_option('plugin/lastfm/user')
            self.password_hash = pylast.md5(settings.get_option('plugin/lastfm/password'))
        except:
            self.username = None
            self.password_hash = None

        ContextPage.__init__(self, theme, base, template, async+['last-played-tracks', 'last-played-artists', 'last-added-tracks', 'last-added-artists', 'most-played-tracks', 'most-played-artists', 'lfm-last-played', 'lfm-top-tracks', 'lfm-top-albums', 'lfm-top-artists'])

    def _last_played_tracks_title(self):
        return "Recently Played Tracks"

    def _last_played_tracks(self, limit=10):
        tracks = get_top_tracks('__last_played', int(limit))
        return "<br/>".join(self.get_track_anchor_from_track(track, img=True) for track in tracks)

    def _last_played_albums_title(self):
        return "Recently Played Albums"

    def _last_played_albums(self, limit=5):
        cds = get_top_albums('__last_played', int(limit))
        if len(cds)>0:
            return self.get_cds_html([x.track for x in search.search_tracks_from_string(
                    ex.exaile().collection, ('album=="%s"' % cd for cd in cds), ['album', 'tracknumber'])])
        return ''

    def _last_played_artists_title(self):
        return "Recently Played Artists"

    def _last_played_artists(self, limit=10):
        artists = get_top_artists('__last_played', int(limit))
        return ', '.join(self.get_artist_anchor(artist) for artist in artists)

    def _last_added_tracks_title(self):
        return "Last Added Tracks"

    def _last_added_tracks(self, limit=10):
        tracks = get_top_tracks('__date_added', int(limit))
        return "<br/>".join(self.get_track_anchor_from_track(track, img=True) for track in tracks)

    def _last_added_albums_title(self):
        return "Last Added Albums"

    def _last_added_albums(self, limit=3):
        cds = get_top_albums('__date_added', int(limit))
        if len(cds)>0:
            return self.get_cds_html([x.track for x in search.search_tracks_from_string(
                    ex.exaile().collection, ('album=="%s"' % cd for cd in cds), ['album', 'tracknumber'])])
        return ''

    def _last_added_artists_title(self):
        return "Last Added Artists"

    def _last_added_artists(self, limit=10):
        artists = get_top_artists('__date_added', int(limit))
        return ', '.join(self.get_artist_anchor(artist) for artist in artists)

    def _most_played_tracks_title(self):
        return "Most Played Tracks"

    def _most_played_tracks(self, limit=10):
        tracks = get_top_tracks('__playcount', int(limit))
        return "<br/>".join(self.get_track_anchor_from_track(track, img=True) for track in tracks)

    def _most_played_albums_title(self):
        return "Most Played Albums"

    def _most_played_albums(self, limit=5):
        cds = get_top_albums('__playcount', int(limit))
        if len(cds)>0:
            return self.get_cds_html([x.track for x in search.search_tracks_from_string(
                    ex.exaile().collection, ('album=="%s"' % cd for cd in cds), ['album', 'tracknumber'])])
        return ''

    def _most_played_artists_title(self):
        return "Most Played Artists"

    def _most_played_artists(self, limit=10):
        artists = get_top_artists('__playcount', int(limit))
        return ', '.join(self.get_artist_anchor(artist) for artist in artists)

    def get_lfm_user(self):
        if not self.user:
            self.user = pylast.User(self.username, self.password_hash, pylast.network)
        return self.user

    def _lfm_last_played_title(self):
        return "Last Scrobbled Tracks"

    def _lfm_last_played(self, limit=10):
        if get_lfm_user():
            tracks = self.get_lfm_user().get_recent_tracks(int(limit))
            return '<br/>'.join(self.get_track_anchor_from_artist_title(tr.track.get_artist(), tr.track.get_title()) for tr in tracks)
        return "Enter your username in the settings"

    def _lfm_top_tracks_title(self):
        return "Your Top Tracks on Last.fm"

    def _lfm_top_tracks(self, period='overall', limit=15):
        if self.get_lfm_user():
            tracks = self.get_lfm_user().get_top_tracks(period, int(limit))
            return '<br/>'.join(self.get_track_anchor_from_artist_title(tr.track.get_artist(), tr.track.get_title()) for tr in tracks)
        return "Enter your username in the settings"

    def _lfm_top_artists_title(self):
        return "Your Top Artists on Last.fm"

    def _lfm_top_artists(self, period='overall', limit=20):
        if self.get_lfm_user():
            artists = self.get_lfm_user().get_top_artists(period,int(limit))
            return ', '.join(self.get_artist_anchor(artist.item.get_name()) for artist in artists)
        return "Enter your username in the settings"

    def _lfm_top_albums_title(self):
        return "Your Top Albums on Last.fm"

    def _lfm_top_albums(self, period='overall', limit=10):
        if self.get_lfm_user():
            cds = [album.get_item().get_title() for album in self.get_lfm_user().get_top_albums(period,int(limit))]
            tracks = []
            if len(cds)>0:
                for cd in cds:
                    tracks+= [x.track for x in search.search_tracks_from_string(
                                ex.exaile().collection, ('album=="%s"' % cd), ['tracknumber'])]
                return self.get_cds_html(tracks)
            return ""
        return "Enter your username in the settings"

class ArtistPage(DefaultPage):
    def __init__(self, theme, artist, base = 'artist://', template ='artist.html', async=[]):
        self.artist = artist
        self.lfm_artist = None

        DefaultPage.__init__(self, theme, base, template, async+['compils', 'albums', 'artist-info', 'artist-img', 'artist-tags', 'similar-artists', 'top-tracks'])

    def get_lfm_artist(self):
        if not self.lfm_artist:
            self.lfm_artist = pylast.Artist(self.artist, pylast.network)
        return self.lfm_artist

    def get_template_fields(self):
        fields = ContextPage.get_template_fields(self)
        for field in fields:
            if field[0] in ['albums', 'compils']:
                fields.remove(field)
                fields.insert(0, field)
        return fields

    def track_in_collection(self, artist, title):
        if artist == self['artist']:
            tracks = [x.track for x in search.search_tracks_from_string(
                    ex.exaile().collection, ('artist=="%s" title=="%s"' % (artist, title)))]
            if len(tracks)>0: return tracks[0]
            else: return None
        else:
            return ContextPage.track_in_collection(self, artist, title)

    def get_text_from_track(self, track):
        if self['artist'] == get_track_tag(track, 'artist', ''):
            return track['title'][0]
        return ContextPage.get_text_from_track(self, track)

    def get_search_text(self, artist, title):
        if self['artist'] == artist:
            return title
        else:
            return ContextPage.get_search_text(self, artist, title)

    def _artist(self):
        return self.artist

    def _artist_img(self, size=pylast.COVER_LARGE):
        try:
            url = self.get_lfm_artist().get_cover_image(size)
            return '<img id="artist-info-img" src="%s"/>' % url
        except:
            return ''

    def _artist_info(self):
        if self.get_lfm_artist():
            bio = self.get_lfm_artist().get_bio_summary()
            return self.LFMInfoParser(self, str(bio), self['artist']).data
        return ''

    def _top_tracks_title(self):
        return 'Top tracks by %s' % self['artist']

    def _top_tracks(self, limit=10):
        if self.get_lfm_artist():
            doc = self.get_lfm_artist().get_top_tracks(int(limit))
            return '<br/>'.join(self.get_track_anchor_from_artist_title(self['artist'], tr.get_item().get_title(), img=True) for tr in doc)
        return ''

    def _artist_tags_title(self):
        return "Tags for %s" % self['artist']

    def _artist_tags(self, limit=10):
        if self.get_lfm_artist():
            doc = self.get_lfm_artist().get_top_tags(int(limit))
            return ', '.join(self.get_tag_anchor(tag.item) for tag in doc)
        return ''

    def _compils_title(self):
        return "Compilations with %s"%self['artist']

    def _compils(self):
        compils = [x.track for x in search.search_tracks_from_string(
                    ex.exaile().collection, '! %s==__null__' % self['artist'])]
        if len(compils)>0:
            return self.get_cds_html([x.track for x in search.search_tracks_from_string(
                    ex.exaile().collection, ('album=="%s"' % compil for compil in compils), ['album', 'tracknumber'])])
        return ''

    def _similar_artists_title(self):
        return "Artists related to %s" % self['artist']

    def _similar_artists(self, limit=10):
        if self.get_lfm_artist():
            sim_artists = self.get_lfm_artist().get_similar(int(limit))
            return ', '.join(self.get_artist_anchor(sim_artist.item) for sim_artist in sim_artists)
        return ''

    def _albums_title(self):
        return "Albums by %s" % self['artist']

    def _albums(self):
        if len(self.artist_tracks) == 0:
            return ''
        else:
            return self.get_cds_html(ex.exaile().collection.search('__compilation==__null__', tracks=self.artist_tracks, sort_fields=['album', 'tracknumber']))

    class LFMInfoParser(HTMLParser.HTMLParser):
        def __init__(self, outer, data, artist):
            HTMLParser.HTMLParser.__init__(self)
            self.outer = outer
            self.artist = artist
            self.data = data
            self.feed(data)
            self.close()

        def handle_starttag(self, tag, attrs):
            global info
            dic = {}
            if tag=='a':
                for attr in attrs:
                    dic[attr[0]] = attr[1]

            if dic.has_key('class') and dic.has_key('href'):
                if dic['class'] == 'bbcode_tag':
                    self.data = self.data.replace('bbcode_tag', 'tag-link', 1)
                    self.data = self.data.replace(dic['href'], self.outer.get_tag_href(dic['href'].split('/')[-1].replace('+', ' ')))
                elif dic['class'] == 'bbcode_album':
                    album = dic['href'].split('/')[-1].replace('+', ' ')
                    self.data = self.data.replace(dic['href'], self.outer.get_album_href(album))
                elif dic['class'] == 'bbcode_track':
                    title = dic['href'].split('/')[-1].replace('+', ' ')
                    href = self.outer.get_track_href_from_artist_title(self.artist, title)
                    if href.find('track://')>-1:
                        self.data = self.data.replace('bbcode_track', 'track-link col', 1)
                    else:
                        self.data = self.data.replace('bbcode_track', 'search-link', 1)
                    self.data = self.data.replace(dic['href'], href)
                elif dic['class'] == 'bbcode_artist':
                    artist = dic['href'].split('/')[-1].replace('+', ' ')
                    if artist_in_collection(artist):
                        self.data = self.data.replace('bbcode_artist', 'artist-link col', 1)
                    else:
                        self.data = self.data.replace('bbcode_artist', 'artist-link', 1)
                    self.data = self.data.replace(dic['href'], self.outer.get_artist_href(artist))
                elif dic['class'] == 'bbcode_place':
                    self.data = self.data.replace(dic['href'], "place://%s" % dic['href'].split('/')[-1].replace('+', ' '))

class TagPage(DefaultPage):

    def __init__(self, theme, tag, base='tag://', template='tag.html', async=[]):
        self.tag = tag
        self.lfm_tag = None

        DefaultPage.__init__(self, theme, base, template, async+['similar-tags', 'top-artists', 'tag-top-tracks', 'tag-top-albums'])
        
    def get_lfm_tag(self):
        if not self.lfm_tag:
            self.lfm_tag = pylast.Tag(self.tag, pylast.network)
        return self.lfm_tag

    def _tag(self):
        return self.tag

    def _similar_tags_title(self):
        return "Tags similar to %s" % self['tag']

    def _similar_tags(self):
        if self.get_lfm_tag():
            tags = self.get_lfm_tag().get_similar()
            return ', '.join(self.get_tag_anchor(tag) for tag in tags[:20])
        return ''

    def _top_artists_title(self):
        return "Top %s artists" % self.tag

    def _top_artists(self):
        if self.get_lfm_tag():
            artists = self.get_lfm_tag().get_top_artists()
            return ', '.join(self.get_artist_anchor(artist.item) for artist in artists[:20])
        return ''

    def _tag_top_tracks_title(self):
        return "Top %s tracks" % self.tag

    def _tag_top_tracks(self):
        if self.get_lfm_tag():
            tracks = self.get_lfm_tag().get_top_tracks()
            return '<br/>'.join(self.get_track_anchor_from_artist_title(track.item.get_artist(), track.item.get_title()) for track in tracks[:15])
        return ''

    def _tag_top_albums_title(self):
        return "Top %s albums" % self.tag

    def _tag_top_albums(self):
        if self.get_lfm_tag():
            albums = self.get_lfm_tag().get_top_albums()
            return '<br/>'.join("%s %s"%(self['album-ico'],self.get_album_anchor_from_artist_title(album.item.get_artist(), album.item.get_name())) for album in albums[:15])
        return ''

class PlayingPage(ArtistPage):

    def __init__(self, theme, track, base='playing://', template='playing.html', async=[]):
        self.track = track
        self.lfm_track = None
        ArtistPage.__init__(self, theme, get_track_tag(self.track, 'artist', 'unknown'),base, template, async+['track-tags', 'suggested-tracks', 'similar-tracks', 'lyrics'])
        event.add_callback(self.refresh_rating, 'rating_changed')

    def get_lfm_track(self):
        if not self.lfm_track:
            self.lfm_track = pylast.Track(get_track_tag(self.track, 'artist', 'unknown'), get_track_tag(self.track, 'title', 'unknown'), pylast.network)
        return self.lfm_track

    def link_clicked(self, link):
        if link[0] == 'rate':
            self.track.set_rating(int(link[1]))
            self.refresh_rating()
            for field in ['rating', 'track-info']:
                if field in self.get_template_fields():
                    event.log_event('field_refresh', self, (field, str(self[field])))
            return True

    def _title(self):
        return get_track_tag(self.track, 'title', 'unknown')

    def _album(self):
        return get_track_tag(self.track, 'album', 'unknown')

    def _track_cover(self):
        cover = get_track_cover(self.track)
        cover_data = get_image_data(cover, (100, 100))
        return "<a id='cover-image' href='%s'><img src='%s'></a>" % (self.get_album_href(self['album']), cover_data)

    def _playcount(self):
        try:
            self['playcount'] = self.track.get_tag_display('__playcount')
            if self['playcount'] == None:
                self['playcount'] = 0
        except:
            self['playcount'] = 0
        return self['playcount']

    def refresh_rating(self, type=None, object=None, data=None):
        self.update_field('rating')
        self.update_field('track-info')

    def _rating(self):
        try:
            self['rating'] = self.track.get_rating()
        except:
            self['rating'] = 0
        self['rating-html'] = self.get_rating_html(self['rating'])
        return self['rating']

    def _rating_html(self):
        self._rating()
        return self['rating-html']

    def _date(self):
        return get_track_tag(self.track, 'date', '')

    def _track_info(self):
        return "%s<br/>%s<br/>Track played %s times<br/>%s<br/>%s" % \
                 (self.get_artist_anchor(self['artist']),self['album'], self['playcount'], self['rating-html'], self['date'])

    def _track_tags_title(self):
        return "Tags for %s" % self['title']

    def _track_tags(self, limit=10):
        if self.get_lfm_track():
            tags = self.get_lfm_track().get_top_tags(limit)
            return ', '.join(self.get_tag_anchor(tag.item) for tag in tags)
        return ''

    def _suggested_tracks_title(self):
        return "Suggested tracks for %s" % self['title']

    def _suggested_tracks(self):
        sim_tracks = ex.exaile().dynamic.find_similar_tracks(self.track, limit=10)
        return '<br/>'.join(self.get_track_anchor_from_track(track, img=True) for track in sim_tracks)

    def _similar_tracks_title(self):
        return 'Tracks similar to %s' % self['title']

    def _similar_tracks(self, limit=10):
        if self.get_lfm_track():
            doc = self.get_lfm_track().get_similar(int(limit))
            return '<br/>'.join(self.get_track_anchor_from_artist_title(str(tr.get_artist()), str(tr.get_title()), img=True) for tr in doc)
        return ''

    def _lyrics_title(self):
        return "Lyrics of %s by %s" % (self['title'],self['artist'])

    def _lyrics(self):
        try:
            l = ex.exaile().lyrics.find_lyrics(self.track)
            l = "%s <br/><br/>from %s" % (l[0].replace('\n', '<br/>'), l[1])
        except:
            l='No lyrics found'
        return l

class LyricsPage(PlayingPage):

    def __init__(self, theme, track, base='lyrics://', template='lyrics.html', async=[]):
        PlayingPage.__init__(self, theme, track, base, template, async)

class ContextPanel(panel.Panel):
    """
        The contextual panel
    """
    ui_info = (BASEDIR+'context.ui', 'ContextPanelWindow')

    def __init__(self, parent):
        panel.Panel.__init__(self, parent, 'contextinfo')

        cachedir = os.path.join(xdg.get_data_dirs()[0], 'context')
        if not os.path.isdir(cachedir):
            os.mkdir(cachedir)

        #TODO last.fm class
        pylast.network = pylast.get_lastfm_network(LFM_API_KEY)
        pylast.network.enable_caching(os.path.join(cachedir, 'lastfm.cache'))

        self.controller = parent

        self._theme = ContextTheme(settings.get_option('context/theme', 'classic'))

        self._browser = BrowserPage(self.builder, self._theme)

        self.setup_widgets()

    def setup_widgets(self):
        self._scrolled_window = Gtk.ScrolledWindow()
        self._scrolled_window.props.hscrollbar_policy = Gtk.PolicyType.AUTOMATIC
        self._scrolled_window.props.vscrollbar_policy = Gtk.PolicyType.AUTOMATIC
        self._scrolled_window.add(self._browser)
        self._scrolled_window.show_all()

        frame = self.builder.get_object('ContextFrame')
        frame.add(self._scrolled_window)
        
def get_preferences_pane():
    return contextprefs

def exaile_ready(object=None, a=None, b=None):
    global PANEL
    PANEL = ContextPanel(xlgui.get_controller().main)
    providers.register('main-panel', PANEL)
    
    event.remove_callback(exaile_ready, 'exaile_loaded')

def enable(exaile):
    """
        Adds 'Contextual' tab to side panel
    """
    if not exaile.loading:
        exaile_ready()
    else:
        event.add_callback(exaile_ready, 'exaile_loaded')
    return True

def disable(exaile):
    """
        Removes tab
    """
    global PANEL
    providers.unregister('main-panel', PANEL)
