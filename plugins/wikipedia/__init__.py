# encoding:utf-8

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import logging
import os
import urllib2

import gi
gi.require_version('WebKit2', '4.0')

from gi.repository import (
    GLib,
    Gtk,
    WebKit2,
)

from xl import (
    common,
    event,
    providers,
    settings
)
from xl.nls import gettext as _
from xlgui import panel

import config
import preferences

log = logging.getLogger('exaile-wikipedia/__init__.py')

WIKIPANEL = None
CURPATH = os.path.realpath(__file__)
BASEDIR = os.path.dirname(CURPATH) + os.path.sep


def enable(exaile):
    config.USER_AGENT = exaile.get_user_agent_string('wikipedia')

    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)


def disable(exaile):
    global WIKIPANEL
    providers.unregister('main-panel', WIKIPANEL)


def _enable(eventname, exaile, nothing):
    global WIKIPANEL
    WIKIPANEL = WikiPanel(exaile.gui.main.window)
    providers.register('main-panel', WIKIPANEL)


def get_preferences_pane():
    return preferences


class BrowserPage(WebKit2.WebView):
    history_length = 6

    def __init__(self, builder):
        WebKit2.WebView.__init__(self)

        self.hometrack = None

        builder.connect_signals(self)
        event.add_callback(self.on_playback_start, 'playback_track_start')

    def destroy(self):
        event.remove_callback(self.on_playback_start, 'playback_track_start')

    def on_playback_start(self, type, player, track):
        self.hometrack = track
        self.load_wikipedia_page(track)

    def on_home_button_clicked(self, button):
        if self.hometrack is not None:
            self.load_wikipedia_page(self.hometrack)

    def on_refresh_button_clicked(self, button):
        self.reload()

    def on_back_button_clicked(self, button):
        self.go_back()

    def on_forward_button_clicked(self, button):
        self.go_forward()

    @common.threaded
    def load_wikipedia_page(self, track):
        if track != self.hometrack:
            return

        artist = track.get_tag_display('artist')
        language = settings.get_option('plugin/wikipedia/language', 'en')
        if language not in config.LANGUAGES:
            log.error('Provided language "%s" not found.' % language)
            language = 'en'

        artist = urllib2.quote(artist.encode('utf-8'), '')
        url = "https://%s.m.wikipedia.org/wiki/Special:Search/%s" % (language, artist)

        try:
            html = common.get_url_contents(url, config.USER_AGENT)
        except urllib2.URLError as e:
            log.error(e)
            log.error(
                "Error occurred when trying to retrieve Wikipedia page "
                "for %s." % artist)
            html = """
                <p style="color: red">No Wikipedia page found for <strong>%s</strong></p>
                """ % artist

        GLib.idle_add(self.load_html, html, url)


class WikiPanel(panel.Panel):
    # Specifies the path to the UI file and the name of the root element
    ui_info = (os.path.dirname(__file__) + "/data/wikipanel.ui", 'wikipanel_window')

    def __init__(self, parent):
        panel.Panel.__init__(self, parent, 'wikipedia', _('Wikipedia'))
        self.parent = parent
        self._browser = BrowserPage(self.builder)
        self.setup_widgets()

    def destroy(self):
        self._browser.destroy()

    def setup_widgets(self):
        self._scrolled_window = Gtk.ScrolledWindow()
        self._scrolled_window.add(self._browser)
        frame = self.builder.get_object('rendering_frame')
        self._scrolled_window.show_all()
        frame.add(self._scrolled_window)
