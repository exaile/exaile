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

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Pango

import os
import webbrowser

from gi.repository import GdkPixbuf

from xl.nls import gettext as _
from xl import (
    common,
    event,
    lyrics,
    player,
    providers,
    settings
)
from xlgui import guiutil
from xlgui.widgets.notebook import NotebookPage

import lyricsviewerprefs

LYRICSVIEWER = None
CURPATH = os.path.realpath(__file__)
BASEDIR = os.path.dirname(CURPATH) + os.path.sep
IMAGEDIR = os.path.join(BASEDIR, "images")

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

def _enable(o1, exaile, o2):
    global LYRICSVIEWER
    LYRICSVIEWER = LyricsViewer(exaile)
    providers.register('main-panel', LYRICSVIEWER)

def disable(exaile):
    global LYRICSVIEWER
    LYRICSVIEWER.remove_callbacks()
    providers.unregister('main-panel', LYRICSVIEWER)
    LYRICSVIEWER = None

def get_preferences_pane():
    return lyricsviewerprefs

class LyricsViewer(object):

    loading_image = 'loading.gif'
    ui = 'lyricsviewer.ui'

    def __init__(self, exaile):
        self.name = 'lyricsviewer'
        self.exaile = exaile
        self.notebook = exaile.gui.panel_notebook
        self.source_url = ""
        self.lyrics_found = []

        self._initialize_widgets()
        self._panel = None

        event.add_ui_callback(self.playback_cb, 'playback_track_start')
        event.add_ui_callback(self.on_track_tags_changed, 'track_tags_changed')
        event.add_ui_callback(self.end_cb, 'playback_player_end')
        event.add_ui_callback(self.search_method_added_cb,
                'lyrics_search_method_added')
        event.add_ui_callback(self.on_option_set, 'plugin_lyricsviewer_option_set')
        #self.style_handler = self.notebook.connect('style-set', self.set_style)

        self.update_lyrics()

    def _initialize_widgets(self):
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(BASEDIR, self.ui))
        builder.connect_signals({
            'on_RefreshButton_clicked' : self.on_refresh_button_clicked,
            'on_LyricsSourceText_motion_notify_event' :
                self.on_lst_motion_event,
            'on_UrlTag_event' : self.on_url_tag_event
        })

        self.lyrics_panel = builder.get_object('LyricsPanel')

        self.lyrics_top_box = builder.get_object('LyricsTopBox')
        self.lyrics_methods_combo = LyricsMethodsComboBox(self.exaile)
        self.lyrics_top_box.pack_start(
                self.lyrics_methods_combo, True, True, 0)
        self.lyrics_methods_combo.connect('changed',
                self.on_combo_active_changed)
        self.lyrics_methods_combo.show()

        self.refresh_button = builder.get_object('RefreshButton')
        self.refresh_button_image = builder.get_object('RefreshLyrics')
        self.loading_animation = GdkPixbuf.PixbufAnimation.new_from_file(
                os.path.join(IMAGEDIR, self.loading_image))

        #track name title text
        self.track_text = builder.get_object('TrackText')
        self.track_text.modify_font(Pango.FontDescription("Bold"))
        self.track_text_buffer = builder.get_object('TrackTextBuffer')
        #trackname end

        #the textview which cointains the lyrics
        self.lyrics_text = builder.get_object('LyricsText')
        self.lyrics_text_buffer = builder.get_object('LyricsTextBuffer')
        self.lyrics_text.modify_font(Pango.FontDescription(
                settings.get_option('plugin/lyricsviewer/lyrics_font')))
        #end lyrictextview

        #text url and source
        self.lyrics_source_text = builder.get_object('LyricsSourceText')
        self.lyrics_source_text.modify_font(
                Pango.FontDescription("Bold Italic"))
        self.lyrics_source_text_buffer = builder.get_object(
                'LyricsSourceTextBuffer')

        #the tag to create a hyperlink in a textbuffer
        lyrics_source_tag_table = builder.get_object('LyricsSourceTagTable')
        self.url_tag = builder.get_object('UrlTag')
        lyrics_source_tag_table.add(self.url_tag)
        #end text url and source

        # TODO: GI: Style must be set via a different mechanism 
        #self.set_style(self.notebook)
        
    #end initialize_widgets
    def on_option_set(self, event, settings, option):
        if option == 'plugin/lyricsviewer/lyrics_font':
            self.lyrics_text.modify_font(Pango.FontDescription(
                    settings.get_option(option)))

    def remove_callbacks(self):
        event.remove_callback(self.playback_cb, 'playback_track_start')
        event.remove_callback(self.on_track_tags_changed, 'track_tags_changed')
        event.remove_callback(self.end_cb, 'playback_player_end')
        event.remove_callback(self.search_method_added_cb,
                'lyrics_search_method_added')
        event.remove_callback(self.on_option_set,
                'plugin_lyricsviewer_option_set')
        #self.notebook.disconnect(self.style_handler)

    def search_method_added_cb(self, eventtype, lyrics, provider):
        self.update_lyrics()

    def on_track_tags_changed(self, eventtype, track, tag):
        if player.PLAYER.current == track and tag in ["artist", "title"]:
            self.update_lyrics()

    def playback_cb(self, eventtype, player, data):
        self.update_lyrics()

    def end_cb(self, eventtype, player, data):
        self.update_lyrics()
    
    def on_lst_motion_event(self, textview, event):
        """
            Catches when the mouse moves on the TextView lyrics_source_text
            If the source url exists changes tooltip and the mouse cursor
            depending on its position.
        """
        tag = None
        window = textview.get_window(Gtk.TextWindowType.TEXT)
        cursor_type = window.get_cursor().get_cursor_type().value_name

        if self.source_url != "":
            x, y = textview.window_to_buffer_coords(Gtk.TextWindowType.TEXT,
                                                    event.x, event.y)
            tag = textview.get_iter_at_location(x, y).get_tags()
            tooltip_text = textview.get_tooltip_text()

            if (cursor_type == "GDK_XTERM" or self.source_url != tooltip_text) \
                    and tag:
                #url_tag affected by the motion event
                window.set_cursor(Gdk.Cursor.new(Gdk.CursorType.HAND2))
                textview.set_tooltip_text(self.source_url)
                return

        if cursor_type == "GDK_HAND2"  and not tag:
            #url_tag not affected by the motion event
            #restore default state
            window.set_cursor(Gdk.Cursor.new(Gdk.CursorType.XTERM))
            self.lyrics_source_text.set_tooltip_text(None)

    def on_url_tag_event(self, tag, widget, event, iter):
        """
            Catches when the user clicks the url_tag .
            Opens a new page (or tab) in the preferred browser.
        """
        if event.type == Gdk.EventType.BUTTON_RELEASE:
            self.open_url(self.source_url)

    @common.threaded
    def open_url(self, url):
        webbrowser.open_new_tab(url)

    def on_refresh_button_clicked(self, button):
        self.update_lyrics(refresh = True)

    def on_combo_active_changed(self, combobox):
        """
            Catches when the user selects an item of the combo.
            Calls the update_lyrics_text if lyrics are cached.
        """
        if self.lyrics_found:
            self.update_lyrics_text()

    def update_lyrics(self, refresh = False):
        self.track_text_buffer.set_text("")
        self.lyrics_text_buffer.set_text("")
        self.lyrics_source_text_buffer.set_text("")
        self.lyrics_found = []
        if player.PLAYER.current:
            self.set_top_box_widgets(False)
            self.get_lyrics(player.PLAYER.current, refresh)
        else:
            self.lyrics_text_buffer.set_text(_('Not playing.'))
            self.set_top_box_widgets(False, True)
        
    @common.threaded
    def get_lyrics(self, track, refresh=False):
        lyrics_found = []
        track_text = ''
        try:
            try:
                track_text = (track.get_tag_raw('artist')[0] + \
                                     " - " + track.get_tag_raw('title')[0])
            except Exception:
                raise lyrics.LyricsNotFoundException
            lyrics_found = lyrics.MANAGER.find_all_lyrics(track, refresh)
        except lyrics.LyricsNotFoundException:
            lyrics_found = []
        finally:
            self._get_lyrics_finish(track, track_text, lyrics_found)
    
    @guiutil.idle_add()
    def _get_lyrics_finish(self, track, track_text, lyrics_found):
        '''Only called from get_lyrics thread, thunk to ui thread'''
        
        if track != player.PLAYER.current:
            return

        self.lyrics_found = lyrics_found
        
        self.track_text_buffer.set_text(track_text)
        self.update_lyrics_text()
        self.set_top_box_widgets(True)

    def update_lyrics_text(self):
        """
            Updates the lyrics text view, showing the lyrics from the
            selected lyrics search method
        """
        lyrics = _("No lyrics found.")
        source = ""
        url = ""
        if self.lyrics_found:
            (index, selected_method) = self.lyrics_methods_combo.\
                    get_active_item()
            for (name, lyr, sou, ur) in self.lyrics_found:
                if name == selected_method or index == 0:
                    lyrics, source, url = lyr, sou, ur
                    break
                
        self.lyrics_text_buffer.set_text(lyrics)
        self.update_source_text(source, url)
    
    def update_source_text(self, source, url):
        """
            Sets the url tag in the source text buffer
            to the value of the source

            :param source: the name to display as url tag
            :param url: the url string of the source
        """
        self.source_url = ""
        if url != "":
            self.lyrics_source_text_buffer.set_text(_("Go to: "))
            iter = self.lyrics_source_text_buffer.get_end_iter()
            self.lyrics_source_text_buffer.insert_with_tags(
                    iter, source, self.url_tag)
            self.source_url = url
        else:
            self.lyrics_source_text_buffer.set_text("")
    
    def set_top_box_widgets(self, state, init = False):
        if state or init:
            self.refresh_button_image.set_from_icon_name(
                    'view-refresh', Gtk.IconSize.BUTTON)
        else:
            self.refresh_button_image.set_from_animation(
                    self.loading_animation)

        self.refresh_button.set_sensitive(state)
        self.lyrics_methods_combo.set_sensitive(state)

    def set_style(self, widget, oldstyle = None):
        """
            Sets lyricsviewer style according to the widget param passed
        """
        states = [Gtk.StateType.NORMAL, Gtk.StateType.ACTIVE, Gtk.StateType.SELECTED]
        widget_style = widget.get_style()
        bg = widget_style.bg
        fg = widget_style.fg

        for state, rstate  in zip(states[::-1], states):
            self.modify_textview_look(self.lyrics_text, state,
                    bg[state].to_string(), fg[state].to_string())
            for textview in (self.lyrics_source_text, self.track_text):
                self.modify_textview_look(textview, state,
                        bg[rstate].to_string(), fg[rstate].to_string())
    
    def modify_textview_look(self, textview, state, base_color, text_color):
        textview.modify_base(state, Gdk.color_parse(base_color))
        textview.modify_text(state, Gdk.color_parse(text_color))

    def get_panel(self):
        '''Returns panel for panel interface'''
        if self._panel is None:    
            self.lyrics_panel.unparent()
            self._panel = NotebookPage(self.lyrics_panel, _('Lyrics'))
        return self._panel

class LyricsMethodsComboBox(Gtk.ComboBoxText, providers.ProviderHandler):
    """
        An extended Gtk.ComboBox class.
        Shows lyrics methods search registered
    """
    def __init__(self, exaile):
        Gtk.ComboBoxText.__init__(self)
        providers.ProviderHandler.__init__(self, 'lyrics')
        
        self.model = self.get_model()
        # Default value, any registered lyrics provider
        self.append_text(_("Any"))

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

