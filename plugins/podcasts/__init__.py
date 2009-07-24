import gtk
from xl import event, common, playlist
from xl import track
from xl.nls import gettext as _
from xlgui import panel, main, commondialogs
from xlgui import guiutil
import xlgui, os, os.path
import _feedparser as fp

PODCASTS = None
CURPATH = os.path.realpath(__file__)
BASEDIR = os.path.dirname(CURPATH)

def enable(exaile):
    if exaile.loading:
        event.add_callback(exaile_ready, 'gui_loaded')
    else:
        exaile_ready(None, exaile, None)

def exaile_ready(event, exaile, nothing):
    global PODCASTS

    if not PODCASTS:
        PODCASTS = PodcastPanel(main.mainwindow().window)
        controller = xlgui.controller()
        controller.panels['podcasts'] = PODCASTS
        controller.add_panel(*PODCASTS.get_panel())

def disable(exaile):
    if PODCASTS:
        conroller = xlgui.controller()
        conroller.remove_panel(PODCASTS.get_panel()[0])
        PODCASTS = None
        PODCASTS.destroy()

class PodcastPanel(panel.Panel):
    gladeinfo = ('file://' + os.path.join(BASEDIR, 'podcasts.glade'), 
        'PodcastPanelWindow')

    def __init__(self, parent):
        panel.Panel.__init__(self, parent, _('Podcasts'))
        
        self._connect_events()

    def _connect_events(self):
        self.xml.signal_autoconnect({
            'on_add_button_clicked': self.on_add_podcast,
        })

    def on_add_podcast(self, *e):
        dialog = commondialogs.TextEntryDialog(_('Enter the URL of the '
            'podcast to add'), _('Open Podcast'))
        dialog.set_transient_for(self.parent)
        dialog.set_position(gtk.WIN_POS_CENTER_ON_PARENT)

        result = dialog.run()
        dialog.hide()

        if result == gtk.RESPONSE_OK:
            url = dialog.get_value()
            self._parse_podcast(url)

    @common.threaded
    def _parse_podcast(self, url):
        d = fp.parse(url)
        entries = d['entries']

        title = d['feed']['title']
        pl = playlist.Playlist(title)

        tracks = []
        for e in entries:
            tr = track.Track()
            tr.set_loc(e.links[0].href)
            date = e['updated_parsed']
            tr['artist'] = title
            tr['title'] = e['title']
            tr['date'] = "%d-%d-%d" % (date.tm_year, date.tm_mon,
                date.tm_mday)
            tracks.append(tr)
           
        pl.add_tracks(tracks)

        self._open_podcast(pl)

    @guiutil.idle_add()
    def _open_podcast(self, pl):
        main.mainwindow().add_playlist(pl)
