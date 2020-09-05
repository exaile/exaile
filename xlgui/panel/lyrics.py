# Copyright (C) 2009-2010 Aren Olson
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

from gi.repository import Gtk
from gi.repository import GLib

from xl.nls import gettext as _
from xl import common, event, player, providers
from xl import settings as xl_settings
from xl import lyrics as xl_lyrics
from xlgui import guiutil, panel
from xlgui.preferences import lyrics as lyricsprefs


class LyricsPanel(panel.Panel):

    # public variable for xlgui.panel.Panel
    ui_info = ('lyrics.ui', 'LyricsPanel')

    def __init__(self, parent, name):
        panel.Panel.__init__(self, parent, name, _('Lyrics'))

        self.__lyrics_found = []
        self.__css_provider = Gtk.CssProvider()

        WIDGET_LIST = [
            'lyrics_top_box',
            'refresh_button',
            'refresh_button_stack',
            'refresh_icon',
            'refresh_spinner',
            'track_text',
            'scrolled_window',
            'lyrics_text',
            'lyrics_source_label',
            'track_text_buffer',
            'lyrics_text_buffer',
        ]
        for name in WIDGET_LIST:
            setattr(
                self,
                '_' + LyricsPanel.__name__ + '__' + name,
                self.builder.get_object(name),
            )
        self.__initialize_widgets()

        event.add_ui_callback(self.__on_playback_track_start, 'playback_track_start')
        event.add_ui_callback(self.__on_track_tags_changed, 'track_tags_changed')
        event.add_ui_callback(self.__on_playback_player_end, 'playback_player_end')
        event.add_ui_callback(
            self.__on_lyrics_search_method_added, 'lyrics_search_method_added'
        )
        event.add_ui_callback(self.__on_option_set, 'plugin_lyricsviewer_option_set')

        self.__update_lyrics()

    def __initialize_widgets(self):
        lyrics_methods_combo = LyricsMethodsComboBox()
        self.__lyrics_top_box.pack_start(lyrics_methods_combo, True, True, 0)
        lyrics_methods_combo.connect('changed', self.__on_combo_active_changed)
        lyrics_methods_combo.show()
        self.__lyrics_methods_combo = lyrics_methods_combo

        track_text_style = Gtk.CssProvider()
        style_context = self.__track_text.get_style_context()
        style_context.add_provider(
            track_text_style, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        track_text_style.load_from_data(b"textview {font-weight: bold; }")

        style_context = self.__lyrics_text.get_style_context()
        style_context.add_provider(
            self.__css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        lyricsprefs.DEFAULT_FONT = (
            self.__lyrics_text.get_default_attributes().font.to_string()
        )
        # trigger initial setup through options
        self.__on_option_set(None, xl_settings, 'plugin/lyricsviewer/lyrics_font')

        self.__refresh_button.connect('clicked', self.__on_refresh_button_clicked)

    def __on_option_set(self, _event, settings, option):
        if option == 'plugin/lyricsviewer/lyrics_font':
            pango_font_str = settings.get_option(option)
            css_from_pango = guiutil.css_from_pango_font_description(pango_font_str)
            data_str = "textview { " + css_from_pango + "; }\n"
            self.__css_provider.load_from_data(data_str.encode('utf-8'))

    def __on_lyrics_search_method_added(self, _eventtype, _lyrics, _provider):
        self.__update_lyrics()

    def __on_track_tags_changed(self, _eventtype, track, tags):
        if player.PLAYER.current == track and tags & {"artist", "title"}:
            self.__update_lyrics()

    def __on_playback_track_start(self, _eventtype, _player, _data):
        self.__update_lyrics()

    def __on_playback_player_end(self, _eventtype, _player, _data):
        self.__update_lyrics()

    def __on_refresh_button_clicked(self, _button):
        """
        Called when the refresh button is clicked
        """
        self.__update_lyrics(refresh=True)

    def __on_combo_active_changed(self, _combobox):
        """
        Catches when the user selects an item of the combo.
        """
        if self.__lyrics_found:
            self.__update_lyrics_text()

    def __update_lyrics(self, refresh=False):
        self.__track_text_buffer.set_text("")
        self.__lyrics_text_buffer.set_text("")
        self.__lyrics_source_label.set_text("")
        self.__lyrics_found = []
        if player.PLAYER.current:
            self.__set_top_box_widgets(False)
            self.__get_lyrics(player.PLAYER.current, refresh)
        else:
            self.__lyrics_text_buffer.set_text(_('Not playing.'))
            self.__set_top_box_widgets(False, True)

    @common.threaded
    def __get_lyrics(self, track, refresh=False):
        lyrics_found = []
        track_text = ''
        try:
            try:
                track_text = (
                    track.get_tag_raw('artist')[0]
                    + " - "
                    + track.get_tag_raw('title')[0]
                )
            except Exception:
                raise xl_lyrics.LyricsNotFoundException
            lyrics_found = xl_lyrics.MANAGER.find_all_lyrics(track, refresh)
        except xl_lyrics.LyricsNotFoundException:
            lyrics_found = []
        finally:
            self.__get_lyrics_finish(track, track_text, lyrics_found)

    @common.idle_add()
    def __get_lyrics_finish(self, track, track_text, lyrics_found):
        '''Only called from __get_lyrics thread, thunk to ui thread'''

        if track != player.PLAYER.current:
            return

        self.__lyrics_found = lyrics_found

        self.__track_text_buffer.set_text(track_text)
        self.__update_lyrics_text()
        self.__set_top_box_widgets(True)

    def __update_lyrics_text(self):
        lyrics = _("No lyrics found.")
        source = ""
        url = ""
        if self.__lyrics_found:
            (index, selected_method) = self.__lyrics_methods_combo.get_active_item()
            for (name, i_lyrics, i_source, i_url) in self.__lyrics_found:
                if name == selected_method or index == 0:
                    lyrics, source, url = i_lyrics, i_source, i_url
                    break
        self.__lyrics_text_buffer.set_text(lyrics)

        if url != "":
            url_text = '<a href="' + url + '">' + source + '</a>'
            self.__lyrics_source_label.set_markup(_("Source: ") + url_text)
        else:
            self.__lyrics_source_label.set_text("")

    def __set_top_box_widgets(self, state, init=False):
        if state or init:
            self.__refresh_spinner.stop()
            self.__refresh_button_stack.set_visible_child(self.__refresh_icon)
        else:
            self.__refresh_button_stack.set_visible_child(self.__refresh_spinner)
            self.__refresh_spinner.start()

        self.__refresh_button.set_sensitive(state)
        self.__lyrics_methods_combo.set_sensitive(state)


class LyricsMethodsComboBox(Gtk.ComboBoxText, providers.ProviderHandler):
    """
    An extended Gtk.ComboBox class.
    Shows lyrics methods search registered
    """

    def __init__(self):
        Gtk.ComboBoxText.__init__(self)
        providers.ProviderHandler.__init__(self, 'lyrics')

        self.model = self.get_model()
        # Default value, any registered lyrics provider
        self.append_text(_("Any source"))

        for provider in self.get_providers():
            self.append_text(provider.display_name)

        self.set_active(0)

    def remove_item(self, name):
        index = self.search_item(name)
        if index:
            GLib.idle_add(self.remove, index)
            return True
        return False

    def append_item(self, name):
        if not self.search_item(name):
            GLib.idle_add(self.append_text, name)
            return True
        return False

    def search_item(self, name):
        index = 0
        for item in self.model:
            if item[0] == name:
                return index
            index += 1
        return False

    def get_active_item(self):
        return self.get_active(), self.get_active_text()

    def on_provider_added(self, provider):
        self.append_item(provider.display_name)

    def on_provider_removed(self, provider):
        self.remove_item(provider.display_name)
