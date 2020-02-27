from hashlib import md5
import logging
import os
import os.path

import feedparser

from gi.repository import GLib
from gi.repository import Gtk

from xl import event, common, playlist, providers
from xl import trax
from xl.nls import gettext as _
from xlgui import panel, main
from xlgui.widgets import dialogs, menu
from xl import xdg

# set up logger
logger = logging.getLogger(__name__)

PODCASTS = None
CURPATH = os.path.realpath(__file__)
BASEDIR = os.path.dirname(CURPATH)


def enable(exaile):
    feedparser.USER_AGENT = exaile.get_user_agent_string('podcasts')
    if exaile.loading:
        event.add_callback(exaile_ready, 'gui_loaded')
    else:
        exaile_ready(None, exaile, None)


def exaile_ready(event, exaile, nothing):
    global PODCASTS

    if not PODCASTS:
        PODCASTS = PodcastPanel(main.mainwindow().window)
        providers.register('main-panel', PODCASTS)


def disable(exaile):
    global PODCASTS

    if PODCASTS:
        providers.unregister('main-panel', PODCASTS)
        PODCASTS = None


class PodcastPanel(panel.Panel):
    ui_info = (os.path.join(BASEDIR, 'podcasts.ui'), 'PodcastPanel')

    def __init__(self, parent):
        panel.Panel.__init__(self, parent, 'podcasts', _('Podcasts'))
        self.podcasts = []
        self.podcast_playlists = playlist.PlaylistManager('podcast_plugin_playlists')

        self._setup_widgets()
        self._connect_events()
        self.podcast_file = os.path.join(
            xdg.get_plugin_data_dir(), 'podcasts_plugin.db'
        )
        self._load_podcasts()

    def _setup_widgets(self):
        self.model = Gtk.ListStore(str, str)
        self.tree = self.builder.get_object('podcast_tree')
        self.tree.set_model(self.model)

        text = Gtk.CellRendererText()
        self.column = Gtk.TreeViewColumn(_('Podcast'))
        self.column.pack_start(text, True)
        self.column.set_expand(True)
        self.column.set_attributes(text, text=0)
        self.tree.append_column(self.column)

        self.status = self.builder.get_object('podcast_statusbar')

        self.menu = menu.Menu(self)
        self.menu.add_simple(_('Refresh Podcast'), self._on_refresh, Gtk.STOCK_REFRESH)
        self.menu.add_simple(_('Delete'), self._on_delete, Gtk.STOCK_DELETE)
        self.menu.attach_to_widget(self.tree)

    @common.idle_add()
    def _set_status(self, message, timeout=0):
        self.status.set_text(message)

        if timeout:
            GLib.timeout_add_seconds(timeout, self._set_status, '', 0)

    def _connect_events(self):
        self.builder.connect_signals({'on_add_button_clicked': self.on_add_podcast})

        self.tree.connect('row-activated', self._on_row_activated)
        self.tree.connect('button-press-event', self._on_button_press)

    def _on_button_press(self, button, event):
        if event.triggers_context_menu():
            self.menu.popup(event)

    def _on_refresh(self, *e):
        (url, title) = self.get_selected_podcast()
        self._parse_podcast(url)

    def _on_delete(self, *e):
        (url, title) = self.get_selected_podcast()
        for item in self.podcasts:
            (title, _url) = item
            if _url == url:
                self.podcasts.remove(item)
                self.podcast_playlists.remove_playlist(
                    md5(url.encode('utf-8')).hexdigest()
                )
                break

        self._save_podcasts()
        self._load_podcasts()

    def on_add_podcast(self, *e):
        dialog = dialogs.TextEntryDialog(
            _('Enter the URL of the ' 'podcast to add'), _('Open Podcast')
        )
        dialog.set_transient_for(self.parent)
        dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

        result = dialog.run()
        dialog.hide()

        if result == Gtk.ResponseType.OK:
            url = dialog.get_value()
            self._parse_podcast(url, True)

    def get_selected_podcast(self):
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()

        url = self.model.get_value(iter, 1)
        title = self.model.get_value(iter, 0)
        return (url, title)

    def _on_row_activated(self, *e):
        (url, title) = self.get_selected_podcast()

        try:
            pl = self.podcast_playlists.get_playlist(
                md5(url.encode('utf-8')).hexdigest()
            )
            self._open_podcast(pl, title)
        except ValueError:
            self._parse_podcast(url)

    @common.threaded
    def _parse_podcast(self, url, add_to_db=False):
        try:
            url = url.replace('itpc://', 'http://')

            self._set_status(_('Loading %s...') % url)
            d = feedparser.parse(url)
            entries = d['entries']

            title = d['feed']['title']

            if add_to_db:
                self._add_to_db(url, title)

            pl = playlist.Playlist(md5(url.encode('utf-8')).hexdigest())

            tracks = []
            for e in entries:
                for link in e.get('enclosures', []):
                    tr = trax.Track(link.href)
                    date = e['updated_parsed']
                    tr.set_tags(
                        artist=title,
                        title='%s: %s' % (e['title'], link.href.split('/')[-1]),
                        date="%d-%02d-%02d" % (date.tm_year, date.tm_mon, date.tm_mday),
                    )
                    tracks.append(tr)

            pl.extend(tracks)
            self._set_status('')

            self._open_podcast(pl, title)
            self.podcast_playlists.save_playlist(pl, overwrite=True)
        except Exception:
            logger.exception("Error loading podcast")
            self._set_status(_('Error loading podcast.'), 2)

    @common.idle_add()
    def _add_to_db(self, url, title):
        self.podcasts.append((title, url))
        self._save_podcasts()
        self._load_podcasts()

    @common.idle_add()
    def _open_podcast(self, pl, title):
        new_pl = playlist.Playlist(title)
        new_pl.extend(pl)
        main.get_playlist_notebook().create_tab_from_playlist(new_pl)

    @common.threaded
    def _load_podcasts(self):
        self._set_status(_("Loading Podcasts..."))
        if not os.path.exists(self.podcast_file):
            self._set_status(_("No configuration present yet"))
            return
        try:
            with open(self.podcast_file) as fp:
                lines = (line.strip() for line in fp.readlines())

            self.podcasts = []

            for line in lines:
                (url, title) = line.split('\t')
                self.podcasts.append((title, url))
        except (IOError, OSError):
            logger.warning('Could not open podcast file')
            self._set_status('')
            return

        self._done_loading_podcasts()

    @common.idle_add()
    def _done_loading_podcasts(self):
        self.model.clear()
        self.podcasts.sort()
        for (title, url) in self.podcasts:
            self.model.append([title, url])

        self._set_status('')

    def _save_podcasts(self):
        try:
            with open(self.podcast_file, 'w') as fp:
                for (title, url) in self.podcasts:
                    fp.write('%s\t%s\n' % (url, title))
        except (OSError, IOError):
            dialogs.error(self.parent, _('Could not save podcast file'))
            return
