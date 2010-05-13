# Copyright (C) 2010 Aren Olson
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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

import gtk, gobject, pango
import os
import webbrowser
from xl.nls import gettext as _
from xl import event, common
from xl.lyrics import LyricsNotFoundException

LYRICSPANEL = None
CURPATH = os.path.realpath(__file__)
BASEDIR = os.path.dirname(CURPATH)+os.path.sep
IMAGEDIR= os.path.join(BASEDIR,"images")

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

def _enable(o1, exaile, o2):
    global LYRICSPANEL
    LYRICSPANEL = LyricsPanel(exaile)
    LYRICSPANEL.show_all()
    exaile.gui.add_panel(LYRICSPANEL, _('Lyrics'))
#I set the style of the text view containing the lyrics here cause
#the style of the top level is not really available until the panel is added.
    LYRICSPANEL.set_lyrics_view_style()

def disable(exaile):
    global LYRICSPANEL
    exaile.gui.remove_panel(LYRICSPANEL)
    LYRICSPANEL = None


class LyricsPanel(gtk.VBox):

    track_title_font='sans bold 10'
    lyrics_font='sans 9'
    source_font='sans bold italic 10'
    bars_base_color='#5d788f'
    bars_text_color='#fefefe'

    loading_image='loading.gif'

    def __init__(self, exaile):
        gtk.VBox.__init__(self, False, 3)
        self.set_border_width(3)
        self.exaile = exaile
        self.url_source=""
        self.lyrics_found=[]
        self._initialize_widgets()

        event.add_callback(self.playback_cb, 'playback_track_start')
        event.add_callback(self.stop_cb, 'playback_track_end')
        event.add_callback(self.end_cb, 'playback_player_end')
        event.add_callback(self.search_method_added_cb, 'lyrics_search_method_added')

        self.update_lyrics(exaile.player)

    def _initialize_widgets(self):
       #lyrics top box contains the refresh button and the combo
        self.lyrics_top_box=gtk.HBox()
        self.lyrics_methods_combo=LyricsMethodsComboBox(self.exaile)
        self.lyrics_top_box.pack_start(self.lyrics_methods_combo, True, True, 0)
        self.lyrics_methods_combo.connect('changed', self.on_combo_active_changed)

        self.refresh_button=gtk.Button()
        self.refresh_button.set_size_request(34, 34)

        self.refresh_button_image=gtk.image_new_from_stock(gtk.STOCK_REFRESH, 2)
        self.refresh_button.set_image(self.refresh_button_image)

        self.setup_top_box()
        self.refresh_button.connect('clicked', self.on_refresh_button_pressed)
        self.refresh_button.set_tooltip_text(_('Refresh Lyrics'))
        self.loading_animation = gtk.gdk.PixbufAnimation(os.path.join(IMAGEDIR, self.loading_image))

        self.lyrics_top_box.pack_start(self.refresh_button, False, False, 0)
        self.pack_start(self.lyrics_top_box, False, False,0)

       #track name title text
        self.track_text_buffer = gtk.TextBuffer()
        self.track_text = TextView(self.track_text_buffer, self.track_title_font)
        self.track_text.modify_look(gtk.STATE_NORMAL, self.bars_base_color, self.bars_text_color)

        self.pack_start(self.track_text, False, False, 0)
       #trackname end

       #scroller for lyricstextview
        self.scroller = gtk.ScrolledWindow()
        self.scroller.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.pack_start(self.scroller, True, True, 5)
       #end scroller

       #the textview which cointains the lyrics
        self.lyrics_text_buffer = gtk.TextBuffer()
        self.lyrics_text=TextView(self.lyrics_text_buffer, self.lyrics_font)

        self.scroller.add(self.lyrics_text)
       #end lyrictextview

       #text url and source
        self.lyrics_source_text_buffer=gtk.TextBuffer()
        self.lyrics_source_text =TextView(self.lyrics_source_text_buffer, self.source_font)
        self.lyrics_source_text.modify_look(gtk.STATE_NORMAL, self.bars_base_color, self.bars_text_color)
       #handling a motion and leave event on the TextView lyrics_source_text
        self._changed_cursor = False
        self.lyrics_source_text.connect("motion-notify-event", self.on_lst_motion_event)
       #the tag to create a hyperlink in a textbuffer
        self.url_tag=self.lyrics_source_text_buffer.create_tag("url")
        self.url_tag.connect("event", self.on_url_tag_event)
        self.url_tag.set_property("underline", True)

        self.pack_start(self.lyrics_source_text, False, False, 0)
       #end text url and source
    #end initialize_widgets

    def search_method_added_cb(self, eventtype, lyrics, provider):
        self.update_lyrics(self.exaile.player)

    def playback_cb(self, eventtype, player, data):
        self.update_lyrics(player)

    def stop_cb(self, eventtype, player, data):
        self.setup_top_box()

    def end_cb(self, eventtype, player, data):
        self.setup_top_box()
        self.update_lyrics(player)

    def on_lst_motion_event(self, textview, event):
        """
            Catches when the mouse move on the TextView lyrics_source_text
            If the buffer is not empty changes tooltip and the mouse cursor
            depending on it's position.
        """
        tag=None
        window=textview.get_window(gtk.TEXT_WINDOW_TEXT)

        if textview.get_buffer().get_char_count():
            x, y, mod = textview.window.get_pointer()
            x, y = textview.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, x, y)

            tag = textview.get_iter_at_location(x, y).get_tags()

            if not self._changed_cursor and tag:
                #url_tag affected by the motion event
                window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))
                textview.set_tooltip_text(self.url_source)
                self._changed_cursor = True
                return

        if self._changed_cursor and not tag :
            #url_tag not affected by the motion event
            #restore default state
            window.set_cursor(gtk.gdk.Cursor(gtk.gdk.XTERM))
            self.lyrics_source_text.set_tooltip_text(None)
            self._changed_cursor = False


    def on_url_tag_event(self, tag, widget, event, iter):
        """
            Catches when the user clicks the url_tag .
            Opens a new page (or tab) in the preferred browser.
        """
        if event.type == gtk.gdk.BUTTON_RELEASE:
            webbrowser.open_new_tab(self.url_source)

    def on_refresh_button_pressed(self, button):
        self.update_lyrics(self.exaile.player)

    def on_combo_active_changed(self, combobox):
        """
            Catches when the user selects an item of the combo.
            Calls the update_lyric_text if lyrics are cached.
        """
        if self.lyrics_found:
            self.update_lyrics_text()

    def update_lyrics(self, player):
        self.lyrics_text_buffer.set_text("")
        self.lyrics_source_text_buffer.set_text("")
        self.lyrics_found=[]
        if player.current:
            self.set_top_box_widgets(False)
            self.get_lyrics(player, player.current)
        else:
            gobject.idle_add(self.lyrics_text_buffer.set_text, _('Not playing.'))
            self.track_text_buffer.set_text("")


    @common.threaded
    def get_lyrics(self, player, track):
        try:
            try:
                text_track=(track.get_tag_raw('artist')[0]+\
                                     " - "+track.get_tag_raw('title')[0])
            except Exception:
                return
            self.track_text_buffer.set_text(text_track)
            self.lyrics_found = self.exaile.lyrics.find_all_lyrics(track)
        except LyricsNotFoundException:
            return
        finally:
            if player.current==track :
                self.update_lyrics_text(player.current, track)
                self.set_top_box_widgets(True)


    def update_lyrics_text(self, track_playing=None, track=None):
        """
            Update the lyrics text view, showing the lyrics from the
            lyrics search method specified by the input param
            @param lyrics_search_method: if not specified means any alowed
        """
        lyrics=_("No lyrics found.")
        source=""
        url=""
        if self.lyrics_found:
            (index, selected_method)=self.lyrics_methods_combo.get_active_item()
            for (name, lyr, sou, ur) in self.lyrics_found:
                if name==selected_method or index == 0:
                    lyrics, source, url=lyr, sou, ur
                    break
        if track_playing==track:
            gobject.idle_add(self.lyrics_text_buffer.set_text, lyrics)
            self.update_source_text(source, url)

    def update_source_text(self, source, url):
        """
            Sets the url tag in the source text buffer
            to the value of the source

            @param source: the name to display as url tag
            @param url: the url string of the source
        """
        self.lyrics_source_text_buffer.set_text("")
        if url!="":
            iter = self.lyrics_source_text_buffer.get_start_iter()
            self.lyrics_source_text_buffer.insert(iter, _("Go to: "))
            iter = self.lyrics_source_text_buffer.get_end_iter()
            self.lyrics_source_text_buffer.insert_with_tags(
                    iter, source, self.url_tag)
            self.url_source=url

    def setup_top_box(self):
        self.refresh_button.set_sensitive(False)
        self.lyrics_methods_combo.set_sensitive(True)
        self.refresh_button_image.set_from_stock(gtk.STOCK_REFRESH, 2)

    def set_top_box_widgets(self, state):
        if state:
            self.refresh_button_image.set_from_stock(gtk.STOCK_REFRESH, 2)
        else:
            self.refresh_button_image.set_from_animation(self.loading_animation)

        self.refresh_button.set_sensitive(state)
        self.lyrics_methods_combo.set_sensitive(state)

    def set_lyrics_view_style(self):
        """
            Sets the style of the lyrics text view with the style of the toplevel
        """
        properties=[gtk.STATE_NORMAL, gtk.STATE_ACTIVE, gtk.STATE_PRELIGHT,  \
                    gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE]
        toplevel_style=self.get_toplevel().style
        for property in properties:
            self.lyrics_text.modify_look(property,
                    toplevel_style.bg[property].to_string(),
                    toplevel_style.fg[property].to_string())



class LyricsMethodsComboBox(gtk.ComboBox):
    """
        An extended gtk.ComboBox class.
        Shows lyrics methods search registered
    """
    def __init__(self, exaile):
        gtk.ComboBox.__init__(self)

        liststore = gtk.ListStore(str)
        self.set_model(liststore)
        cell = gtk.CellRendererText()
        self.pack_start(cell, True)
        self.add_attribute(cell, 'text', 0)
        self.model=self.get_model()
        #default value, any registered providers.
        self.append_text(_("Any"))

        methods=exaile.lyrics.get_method_names()
        for method in methods:
            self.append_text(method)

        self.set_active(0)

        event.add_callback(self.search_method_added_cb,
                'lyrics_search_method_added')

        event.add_callback(self.search_method_removed_cb,
                'lyrics_search_method_removed')

    def search_method_added_cb(self, eventtype, lyrics, provider):
        self.append_item(provider.display_name)

    def search_method_removed_cb(self, eventtype, lyrics, provider):
        self.remove_item(provider.display_name)

    def remove_item(self, name):
        index=self.search_item(name)
        if index:
            gobject.idle_add(self.remove_text, index)
            return True
        return False

    def append_item(self, name):
        if not self.search_item(name):
            gobject.idle_add(self.append_text, name)
            return True
        return False

    def search_item(self, name):
        index=0
        for item in self.model:
            if item[0]==name:
                return index
            index+=1
        return False

    def get_active_item(self):
        active = self.get_active()
        if active >= 0:
            return (active, self.model[active][0])
        else:
            return (None, None)

class TextView(gtk.TextView):
    def __init__(self, text_buffer, font_description):
        gtk.TextView.__init__(self, text_buffer)
        self.set_cursor_visible(False)
        self.set_editable(False)
        self.set_wrap_mode(gtk.WRAP_WORD)
        self.set_justification(gtk.JUSTIFY_CENTER)
        self.set_left_margin(3)
        self.set_right_margin(3)
        self.modify_font(pango.FontDescription(font_description))

    def modify_look(self, state, base_color, text_color):
        self.modify_base(state, gtk.gdk.color_parse(base_color))
        self.modify_text(state, gtk.gdk.color_parse(text_color))

