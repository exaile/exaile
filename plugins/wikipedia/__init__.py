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
import urllib.error
import urllib.parse

from gi.repository import Gtk
from gi.repository import GLib

from xl import common, event, providers, settings
from xl.nls import gettext as _
from xlgui import panel

from . import preferences

import gi

gi.require_version('WebKit2', '4.0')
from gi.repository import WebKit2


log = logging.getLogger(__name__)

# fmt: off
LANGUAGES = ["ab", "aa", "af", "ak", "sq", "am", "ar", "an", "hy", "as", "av",
             "ae", "ay", "az", "bm", "ba", "eu", "be", "bn", "bh", "bi", "bs", "br", "bg",
             "my", "ca", "ch", "ce", "ny", "cv", "kw", "co", "cr", "hr", "cs", "da", "dv",
             "nl", "dz", "en", "eo", "et", "ee", "fo", "fj", "fi", "fr", "ff", "gl", "ka",
             "de", "el", "gn", "gu", "ht", "ha", "he", "hz", "hi", "ho", "hu", "ia", "id",
             "ie", "ga", "ig", "ik", "io", "is", "it", "iu", "jv", "kl", "kn", "kr", "kk",
             "km", "ki", "rw", "ky", "kv", "kg", "kj", "la", "lb", "lg", "li", "ln", "lo",
             "lt", "lv", "gv", "mk", "mg", "ml", "mt", "mi", "mr", "mh", "mn", "na", "nv",
             "nb", "nd", "ne", "ng", "nn", "no", "ii", "nr", "oc", "oj", "cu", "om", "or",
             "os", "pi", "fa", "pl", "ps", "pt", "qu", "rm", "rn", "ro", "ru", "sa", "sc",
             "se", "sm", "sg", "sr", "gd", "sn", "si", "sk", "sl", "so", "st", "es", "su",
             "sw", "ss", "sv", "ta", "te", "th", "ti", "bo", "tk", "tl", "tn", "to", "tr",
             "ts", "tw", "ty", "uk", "ur", "ve", "vi", "vk", "vo", "wa", "cy", "wo", "fy",
             "xh", "yi", "yo", "za", "zu"]
# fmt: on


class WikipediaPlugin:

    __exaile = None
    __wiki_panel = None

    def enable(self, exaile):
        self.__exaile = exaile

    def disable(self, _exaile):
        providers.unregister('main-panel', self.__wiki_panel)
        self.__wiki_panel.destroy()
        self.__exaile = None
        self.__wiki_panel = None

    def on_gui_loaded(self):
        user_agent = self.__exaile.get_user_agent_string('wikipedia')
        self.__wiki_panel = WikiPanel(self.__exaile.gui.main.window, user_agent)
        providers.register('main-panel', self.__wiki_panel)

    def get_preferences_pane(self):
        return preferences


plugin_class = WikipediaPlugin


class BrowserPage(WebKit2.WebView):
    def __init__(self, builder, user_agent):
        WebKit2.WebView.__init__(self)

        self.hometrack = None
        self.__user_agent = user_agent

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
        if language not in LANGUAGES:
            log.error('Provided language "%s" not found.' % language)
            language = 'en'

        artist = urllib.parse.quote(artist.encode('utf-8'), '')
        url = "https://%s.m.wikipedia.org/wiki/Special:Search/%s" % (language, artist)

        try:
            html = common.get_url_contents(url, self.__user_agent)
        except urllib.error.URLError as e:
            log.error(e)
            log.error(
                "Error occurred when trying to retrieve Wikipedia page "
                "for %s." % artist
            )
            html = (
                """
                <p style="color: red">No Wikipedia page found for <strong>%s</strong></p>
                """
                % artist
            )

        GLib.idle_add(self.load_html, html, url)


class WikiPanel(panel.Panel):
    # Specifies the path to the UI file and the name of the root element
    ui_info = (os.path.dirname(__file__) + "/data/wikipanel.ui", 'WikiPanel')

    def __init__(self, parent, user_agent):
        panel.Panel.__init__(self, parent, 'wikipedia', _('Wikipedia'))
        self.parent = parent
        self._browser = BrowserPage(self.builder, user_agent)
        self.setup_widgets()

    def destroy(self):
        self._browser.destroy()

    def setup_widgets(self):
        self._scrolled_window = Gtk.ScrolledWindow()
        self._scrolled_window.add(self._browser)
        frame = self.builder.get_object('rendering_frame')
        self._scrolled_window.show_all()
        frame.add(self._scrolled_window)
