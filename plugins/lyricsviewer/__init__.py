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

import gtk
import glib
import pango
import os
import webbrowser

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

import lyricsviewerprefs

LYRICSPANEL = None
CURPATH = os.path.realpath(__file__)
BASEDIR = os.path.dirname(CURPATH) + os.path.sep
IMAGEDIR = os.path.join(BASEDIR, "images")

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

def _enable(o1, exaile, o2):
    global LYRICSPANEL
    global LYRICSVIEWER
    LYRICSVIEWER = LyricsViewer(exaile)
    LYRICSPANEL = LYRICSVIEWER.get_panel()
    exaile.gui.add_panel(LYRICSPANEL, _('Lyrics'))

def disable(exaile):
    global LYRICSPANEL
    global LYRICSVIEWER
    LYRICSVIEWER.remove_callbacks()
    exaile.gui.remove_panel(LYRICSPANEL)
    LYRICSVIEWER = None
    LYRICSPANEL = None

def get_preferences_pane():
    return lyricsviewerprefs

class LyricsViewer(object):

    loading_image = 'loading.gif'
    ui = 'lyricsviewer.ui'

    def __init__(self, exaile):
        self.exaile = exaile
        self.notebook = exaile.gui.panel_notebook
        self.source_url = ""
        self.lyrics_found = []

        self._initialize_widgets()
        self._lyrics_id = 0

        event.add_callback(self.playback_cb, 'playback_track_start')
        event.add_callback(self.on_track_tags_changed, 'track_tags_changed')
        event.add_callback(self.end_cb, 'playback_player_end')
        event.add_callback(self.search_method_added_cb,
                'lyrics_search_method_added')
        event.add_callback(self.on_option_set, 'plugin_lyricsviewer_option_set')
        self.style_handler = self.notebook.connect('style-set', self.set_style)

        self.update_lyrics()

    def _initialize_widgets(self):
        builder = gtk.Builder()
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
        self.loading_animation = gtk.gdk.PixbufAnimation(
                os.path.join(IMAGEDIR, self.loading_image))

       #track name title text
        self.track_text = builder.get_object('TrackText')
        self.track_text.modify_font(pango.FontDescription("Bold"))
        self.track_text_buffer = builder.get_object('TrackTextBuffer')
       #trackname end

       #the textview which cointains the lyrics
        self.lyrics_text = builder.get_object('LyricsText')
        self.lyrics_text_buffer = builder.get_object('LyricsTextBuffer')
        self.lyrics_text.modify_font(pango.FontDescription(
                settings.get_option('plugin/lyricsviewer/lyrics_font')))
       #end lyrictextview

       #text url and source
        self.lyrics_source_text = builder.get_object('LyricsSourceText')
        self.lyrics_source_text.modify_font(
                pango.FontDescription("Bold Italic"))
        self.lyrics_source_text_buffer = builder.get_object(
                'LyricsSourceTextBuffer')

        #the tag to create a hyperlink in a textbuffer
        lyrics_source_tag_table = builder.get_object('LyricsSourceTagTable')
        self.url_tag = builder.get_object('UrlTag')
        lyrics_source_tag_table.add(self.url_tag)
       #end text url and source

        self.set_style(self.notebook)
    #end initialize_widgets
    def on_option_set(self, event, settings, option):
        if option == 'plugin/lyricsviewer/lyrics_font':
            self.lyrics_text.modify_font(pango.FontDescription(
                    settings.get_option(option)))

    def remove_callbacks(self):
        event.remove_callback(self.playback_cb, 'playback_track_start')
        event.remove_callback(self.on_track_tags_changed, 'track_tags_changed')
        event.remove_callback(self.end_cb, 'playback_player_end')
        event.remove_callback(self.search_method_added_cb,
                'lyrics_search_method_added')
        event.remove_callback(self.on_option_set,
                'plugin_lyricsviewer_option_set')
        self.notebook.disconnect(self.style_handler)

    def search_method_added_cb(self, eventtype, lyrics, provider):
        self.update_lyrics()

    def on_track_tags_changed(self, eventtype, track, tag):
         if player.PLAYER.current == track and tag in ["artist", "title"]:
             self.update_lyrics()

    def playback_cb(self, eventtype, player, data):
        self.update_lyrics()

    def end_cb(self, eventtype, player, data):
        self.update_lyrics()

    @guiutil.idle_add()
    def on_lst_motion_event(self, textview, event):
        """
            Catches when the mouse moves on the TextView lyrics_source_text
            If the source url exists changes tooltip and the mouse cursor
            depending on its position.
        """
        tag = None
        window = textview.get_window(gtk.TEXT_WINDOW_TEXT)
        cursor_type = window.get_cursor().type.value_name

        if self.source_url != "":
            x, y, mod = window.get_pointer()
            x, y = textview.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, x, y)
            tag = textview.get_iter_at_location(x, y).get_tags()
            tooltip_text = textview.get_tooltip_text()

            if (cursor_type == "GDK_XTERM" or self.source_url != tooltip_text) \
                    and tag:
                #url_tag affected by the motion event
                window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))
                textview.set_tooltip_text(self.source_url)
                return

        if cursor_type == "GDK_HAND2"  and not tag:
            #url_tag not affected by the motion event
            #restore default state
            window.set_cursor(gtk.gdk.Cursor(gtk.gdk.XTERM))
            self.lyrics_source_text.set_tooltip_text(None)

    def on_url_tag_event(self, tag, widget, event, iter):
        """
            Catches when the user clicks the url_tag .
            Opens a new page (or tab) in the preferred browser.
        """
        if event.type == gtk.gdk.BUTTON_RELEASE:
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
            self.update_lyrics_text(self._lyrics_id)

    def update_lyrics(self, refresh = False):
        def do_update(refresh):
            self.track_text_buffer.set_text("")
            self.lyrics_text_buffer.set_text("")
            self.lyrics_source_text_buffer.set_text("")
            self.lyrics_found = []
            if player.PLAYER.current:
                self.set_top_box_widgets(False)
                self.get_lyrics(player.PLAYER.current, self._lyrics_id, refresh)
            else:
                self.lyrics_text_buffer.set_text(_('Not playing.'))
                self.set_top_box_widgets(False, True)
            return False

        if self._lyrics_id != 0:
            glib.source_remove(self._lyrics_id)
        self._lyrics_id = glib.idle_add(do_update, refresh)

    @common.threaded
    def get_lyrics(self, track, lyrics_id, refresh = False):
        lyrics_found = []
        try:
            try:
                text_track = (track.get_tag_raw('artist')[0] + \
                                     " - " + track.get_tag_raw('title')[0])
            except Exception:
                raise lyrics.LyricsNotFoundException
            self.track_text_buffer.set_text(text_track)
            lyrics_found = lyrics.MANAGER.find_all_lyrics(track, refresh)
        except lyrics.LyricsNotFoundException:
            lyrics_found = []
            return
        finally:
            if self._lyrics_id == lyrics_id:
                self.lyrics_found = lyrics_found
                self.update_lyrics_text(lyrics_id)
                self.set_top_box_widgets(True)

    def update_lyrics_text(self, lyrics_id):
        """
            Updates the lyrics text view, showing the lyrics from the
            selected lyrics search method

            :param lyrics_id: id of the lyrics found
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
        if self._lyrics_id == lyrics_id:
            glib.idle_add(self.lyrics_text_buffer.set_text, lyrics)
            self.update_source_text(source, url)

    @guiutil.idle_add()
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

    @guiutil.idle_add()
    def set_top_box_widgets(self, state, init = False):
        if state or init:
            self.refresh_button_image.set_from_icon_name(
                    'view-refresh', gtk.ICON_SIZE_BUTTON)
        else:
            self.refresh_button_image.set_from_animation(
                    self.loading_animation)

        self.refresh_button.set_sensitive(state)
        self.lyrics_methods_combo.set_sensitive(state)

    def set_style(self, widget, oldstyle = None):
        """
            Sets lyricsviewer style according to the widget param passed
        """
        states = [gtk.STATE_NORMAL, gtk.STATE_ACTIVE, gtk.STATE_SELECTED]
        widget_style = widget.get_style()
        bg = widget_style.bg
        fg = widget_style.fg

        for state, rstate  in zip(states[::-1], states):
            self.modify_textview_look(self.lyrics_text, state,
                    bg[state].to_string(), fg[state].to_string())
            for textview in (self.lyrics_source_text, self.track_text):
                self.modify_textview_look(textview, state,
                        bg[rstate].to_string(), fg[rstate].to_string())

    @guiutil.idle_add()
    def modify_textview_look(self, textview, state, base_color, text_color):
        textview.modify_base(state, gtk.gdk.color_parse(base_color))
        textview.modify_text(state, gtk.gdk.color_parse(text_color))

    def get_panel(self):
        self.lyrics_panel.unparent()
        return(self.lyrics_panel)

class LyricsMethodsComboBox(gtk.ComboBox, providers.ProviderHandler):
    """
        An extended gtk.ComboBox class.
        Shows lyrics methods search registered
    """
    def __init__(self, exaile):
        gtk.ComboBox.__init__(self)
        providers.ProviderHandler.__init__(self, 'lyrics')

        liststore = gtk.ListStore(str)
        self.set_model(liststore)
        cell = gtk.CellRendererText()
        self.pack_start(cell, True)
        self.add_attribute(cell, 'text', 0)
        self.model = self.get_model()
        # Default value, any registered lyrics provider
        self.append_text(_("Any"))

        for provider in self.get_providers():
            self.append_text(provider.display_name)

        self.set_active(0)

    def remove_item(self, name):
        index = self.search_item(name)
        if index:
            glib.idle_add(self.remove_text, index)
            return True
        return False

    def append_item(self, name):
        if not self.search_item(name):
            glib.idle_add(self.append_text, name)
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
        active = self.get_active()
        if active >= 0:
            return (active, self.model[active][0])
        else:
            return (None, None)

    def on_provider_added(self, provider):
        self.append_item(provider.display_name)

    def on_provider_removed(self, provider):
        self.remove_item(provider.display_name)

