# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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

from xl.nls import gettext as _
import pygtk, pygst
pygtk.require('2.0')
pygst.require('0.10')
import gst, logging
import gtk, gtk.glade, gobject, pango
from xl import xdg, event, track, settings, common
import xl.playlist
from xlgui import playlist, cover, guiutil, commondialogs
import xl.playlist, re, os, threading

settings = settings.SettingsManager.settings
logger = logging.getLogger(__name__)

class PlaybackProgressBar(object):
    def __init__(self, bar, player):
        self.bar = bar
        self.player = player
        self.timer_id = None
        self.seeking = False
        self.player = player

        self.bar.set_text(_('Not Playing'))
        self.bar.connect('button-press-event', self.seek_begin)
        self.bar.connect('button-release-event', self.seek_end)
        self.bar.connect('motion-notify-event', self.seek_motion_notify)

        event.add_callback(self.playback_start, 'playback_start', player)
        event.add_callback(self.playback_end, 'playback_end', player)

    def destroy(self):
        event.remove_callback(self.playback_start, 'playback_start', self.player)
        event.remove_callback(self.playback_end, 'playback_end', self.player)

    def seek_begin(self, *e):
        self.seeking = True

    def seek_end(self, widget, event):
        mouse_x, mouse_y = event.get_coords()
        progress_loc = self.bar.get_allocation()

        value = mouse_x / progress_loc.width
        if value < 0: value = 0
        if value > 1: value = 1

        track = self.player.current
        if not track or not track.is_local(): return
        length = track.get_duration()

        seconds = float(value * length)
        self.player.seek(seconds)
        self.seeking = False
        self.bar.set_fraction(value)
        remaining_seconds = length - seconds
        self.bar.set_text("%d:%02d / %d:%02d" % ((seconds / 60), 
            (seconds % 60), (remaining_seconds / 60), (remaining_seconds % 60))) 
#        self.emit('seek', seconds)

    def seek_motion_notify(self, widget, event):
        track = self.player.current
        if not track or not track.is_local(): return

        mouse_x, mouse_y = event.get_coords()
        progress_loc = self.bar.get_allocation()

        value = mouse_x / progress_loc.width

        if value < 0: value = 0
        if value > 1: value = 1

        self.bar.set_fraction(value)
        length = track.get_duration()
        seconds = float(value * length)
        remaining_seconds = length - seconds
        self.bar.set_text("%d:%02d / %d:%02d" % ((seconds / 60), 
            (seconds % 60), (remaining_seconds / 60), (remaining_seconds % 60))) 
       
    def playback_start(self, type, player, object):
        self.timer_id = gobject.timeout_add(1000, self.timer_update)

    def playback_end(self, type, player, object):
        if self.timer_id: gobject.source_remove(self.timer_id)
        self.timer_id = None
        self.bar.set_text(_('Not Playing'))
        self.bar.set_fraction(0)

    def timer_update(self, *e):
        track = self.player.current
        if not track: return

        if not track.is_local():
            self.bar.set_text('Streaming...')
            return
        length = track.get_duration()

        self.bar.set_fraction(self.player.get_progress())

        seconds = self.player.get_time()
        remaining_seconds = length - seconds
        self.bar.set_text("%d:%02d / %d:%02d" %
            ( seconds // 60, seconds % 60, remaining_seconds // 60,
            remaining_seconds % 60))

        return True

# Reduce the notebook tabs' close button padding size.
gtk.rc_parse_string("""
    style "thinWidget" {
        xthickness = 0
        ythickness = 0
    }
    widget "*.tabCloseButton" style "thinWidget"
    """)
class NotebookTab(gtk.EventBox):
    """
        A notebook tab, complete with a close button
    """
    def __init__(self, main, notebook, title, page):
        """
            Initializes the tab
        """
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)

        self.connect('button_press_event', self.on_button_press)

        self.main = main
        self.nb = notebook
        self.title = title
        self.page = page
        self.tips = gtk.Tooltips()

        self.hbox = hbox = gtk.HBox(False, 2)
        self.add(hbox)

        self.label = gtk.Label(title)
        hbox.pack_start(self.label, False, False)

        self.button = btn = gtk.Button()
        btn.set_name('tabCloseButton')
        btn.set_relief(gtk.RELIEF_NONE)
        btn.set_focus_on_click(False)
        btn.connect('clicked', self.do_close)
        btn.connect('button_press_event', self.on_button_press)
        self.tips.set_tip(btn, _("Close Tab"))
        image = gtk.Image()
        image.set_from_stock('gtk-close', gtk.ICON_SIZE_MENU)
        btn.add(image)
        hbox.pack_end(btn, False, False)

        self.show_all()

    def on_button_press(self, widget, event):
        """
            Called when the user clicks on the tab
        """
        pass

    def do_close(self, *args):
        """
            Called when the user clicks the close button on the tab
        """
        if self.page.on_closing():
            num = self.nb.page_num(self.page)
            self.nb.remove_page(num)

class MainWindow(object):
    """
        Main Exaile Window
    """
    def __init__(self, controller, xml, settings, collection, 
        player, queue, covers):
        """
            Initializes the main window

            @param controller: the main gui controller
        """
        from xlgui import osd
        self.controller = controller
        self.settings = settings
        self.covers = covers
        self.collection =  collection
        self.player = player
        self.queue = queue
        self.current_page = -1 

        self.xml = xml
        self.window = self.xml.get_widget('ExaileWindow')
        self.window.set_title(_('Exaile'))
        self.playlist_notebook = self.xml.get_widget('playlist_notebook')
        self.playlist_notebook.remove_page(0)
        self.splitter = self.xml.get_widget('splitter')

        self._setup_position()
        self._setup_widgets()
        self._setup_hotkeys()
        self._connect_events()
        self.osd = osd.OSDWindow(self.settings, self.cover,
            self.covers, self.player)
        self.tab_manager = xl.playlist.PlaylistManager(
            'saved_tabs')
        self.load_saved_tabs()

    def load_saved_tabs(self):
        """
            Loads the saved tabs
        """
        if not self.settings.get_option('playlist/open_last', True):
            self.add_playlist()
            return
        names = self.tab_manager.list_playlists()
        if not names:
            self.add_playlist()
            return

        count = -1
        count2 = 0
        names.sort()
        for i, name in enumerate(names):
            pl = self.tab_manager.get_playlist(name)
            pl.name = re.sub(r'order\d\.', '', pl.name)
            
            if pl.name.startswith('current.'):
                count = i
                pl.name = pl.name[len('current.'):]
                if self.queue.current_playlist == None:
                    self.queue.set_current_playlist(
                            self.add_playlist(pl).playlist )
            elif pl.name.startswith('playing.'):
                count2 = i
                pl.name = pl.name[len('playing.'):]
                self.queue.set_current_playlist(
                        self.add_playlist(pl).playlist )
            else:
                self.add_playlist(pl)

        # If there's no selected playlist saved, use the currently 
        # playing
        if count == -1:
            count = count2 

        self.playlist_notebook.set_current_page(count)

    def save_current_tabs(self):
        """
            Saves the open tabs
        """
        # first, delete the current tabs
        names = self.tab_manager.list_playlists()
        for name in names:
            os.remove(os.path.join(self.tab_manager.playlist_dir, name))
            self.tab_manager.remove_playlist(name)

        for i in range(self.playlist_notebook.get_n_pages()):
            pl = self.playlist_notebook.get_nth_page(i).playlist
            tag = ''
            if pl is self.queue.current_playlist:
                tag = 'playing.'
            elif i == self.playlist_notebook.get_current_page():
                tag = 'current.'
            pl.name = "order%d.%s%s" % (i, tag, pl.name)
            self.tab_manager.save_playlist(pl, True)            

    def add_playlist(self, pl=None):
        """
            Adds a playlist to the playlist tab

            @param pl: the xl.playlist.Playlist instance to add
        """
        if pl is None:
            pl = xl.playlist.Playlist()
        name = pl.name
        pl = playlist.Playlist(self, self.controller, pl)
        
        # make sure the name isn't too long
        if len(name) > 20:
            name = name[:20] + "..."

        tab = NotebookTab(self, self.playlist_notebook, name, pl)
        self.playlist_notebook.append_page(pl,
            tab)
        self.playlist_notebook.set_current_page(
            self.playlist_notebook.get_n_pages() - 1)
        self.set_mode_toggles()

        return pl

    def _setup_hotkeys(self):
        """
            Sets up accelerators that haven't been set up in glade
        """
        hotkeys = (
            ('<Control>W', lambda *e: self.close_playlist_tab()),
            ('<Control>C', lambda *e: self.on_clear_playlist()),
        )

        self.accel_group = gtk.AccelGroup()
        for key, function in hotkeys:
            key, mod = gtk.accelerator_parse(key)
            self.accel_group.connect_group(key, mod, gtk.ACCEL_VISIBLE,
                function)
        self.window.add_accel_group(self.accel_group)

    def _setup_widgets(self):
        """
            Sets up the various widgets
        """
        self.xml.get_widget('volume_slider').set_value(self.player.get_volume())
        self.shuffle_toggle = self.xml.get_widget('shuffle_button')
        self.shuffle_toggle.set_active(self.settings.get_option('playback/shuffle',
            False))
        self.repeat_toggle = self.xml.get_widget('repeat_button')
        self.repeat_toggle.set_active(self.settings.get_option('playback/repeat',
            False))
        self.dynamic_toggle = self.xml.get_widget('dynamic_button')
        self.dynamic_toggle.set_active(self.settings.get_option('playback/dynamic',
            False))

        # cover box
        self.cover_event_box = self.xml.get_widget('cover_event_box')
        self.cover = cover.CoverWidget(self, self.controller.exaile.covers,
            self.controller.exaile.player)
        self.cover_event_box.add(self.cover)
        self.track_title_label = self.xml.get_widget('track_title_label')
        attr = pango.AttrList()
        attr.change(pango.AttrWeight(pango.WEIGHT_BOLD, 0, 800))
        attr.change(pango.AttrSize(12500, 0, 600))
        self.track_title_label.set_attributes(attr)
        self.track_info_label = self.xml.get_widget('track_info_label')

        self.progress_bar = PlaybackProgressBar(
            self.xml.get_widget('playback_progressbar'),
            self.controller.exaile.player)

        # playback buttons
        bts = ('play', 'next', 'prev', 'stop')
        for button in bts:
            setattr(self, '%s_button' % button,
                self.xml.get_widget('%s_button' % button))
        
        self.stop_button.connect('button-press-event',
            self.on_stop_buttonpress)
        self.status = guiutil.StatusBar(self.xml.get_widget('left_statuslabel'))
        self.track_count_label = self.xml.get_widget('track_count_label')

        # search filter
        box = self.xml.get_widget('playlist_search_entry_box')
        self.filter = guiutil.SearchEntry()
        self.filter.connect('activate', self.on_playlist_search)
        box.pack_start(self.filter.entry, True, True)

        self.rating_combo = self.xml.get_widget('rating_combo_box')
        self.rating_combo.set_active(0)
        self.rating_combo.set_sensitive(False)
        self.rating_id = self.rating_combo.connect('changed',
            self.set_current_track_rating)

    def set_current_track_rating(self, *e):
        """
            Sets the currently playing track's rating
        """
        track = self.player.current
        if not track:
            return

        rating = int(self.rating_combo.get_active())
        steps = self.settings.get_option("miscellaneous/rating_steps", 5)

        track['rating'] = float((100.0*rating)/steps)

        self.update_rating_combo(rating)

    def update_rating_combo(self, rating=None):
        """
            Updates the rating combo box
        """
        track = None
        if rating is None:
            track = self.player.current
            if not track: return
            rating = track.get_rating()

        if self.rating_id:
            self.rating_combo.disconnect(self.rating_id)

        self.rating_combo.set_active(rating)
        self.rating_id = self.rating_combo.connect('changed',
            self.set_current_track_rating)
        self.get_selected_playlist().queue_draw()

    def on_playlist_search(self, *e):
        """
            Filters the currently selected playlist
        """
        pl = self.get_selected_playlist()
        if pl:
            pl.search(self.filter.get_text())

    def on_volume_changed(self, range):
        self.settings['player/volume'] = range.get_value()
        self.player.set_volume(range.get_value())

    def on_stop_buttonpress(self, widget, event):
        """
            Called when the user clicks on the stop button.  We're looking for
            a right click so we can display the SPAT menu
        """
        if event.button != 3: return
        menu = guiutil.Menu()
        menu.append(_("Toggle: Stop after selected track"), self.on_spat_clicked,
            'gtk-stop')
        menu.popup(None, None, None, event.button, event.time)

    def on_spat_clicked(self, *e):
        """
            Called when the user clicks on the SPAT item
        """
        queue = self.controller.exaile.queue
        tracks = self.get_selected_playlist().get_selected_tracks()
        if not tracks: return
        track = tracks[0]

        if track == queue.stop_track:
            queue.stop_track = None
        else:
            queue.stop_track = track

        self.get_selected_playlist().list.queue_draw()

    def update_track_counts(self):
        """
            Updates the track count information
        """
        if not self.get_selected_playlist(): return

        message = "%d showing, %d in collection" \
            % (len(self.get_selected_playlist().playlist), 
               self.collection.get_count())
        
        queuecount = len(self.queue)
        if queuecount:
            message += " : %d queued" % queuecount

        self.track_count_label.set_label(message)

    def _connect_events(self):
        """
            Connects the various events to their handlers
        """
        self.splitter.connect('notify::position', self.configure_event)
        self.xml.signal_autoconnect({
            'on_configure_event':   self.configure_event,
            'on_window_state_event': self.window_state_change_event,
            'on_delete_event':      self.delete_event,
            'on_quit_item_activated': self.delete_event,
            'on_playlist_notebook_switch':  self.playlist_switch_event,
            'on_play_button_clicked': self.on_play_clicked,
            'on_next_button_clicked':
                lambda *e: self.controller.exaile.queue.next(),
            'on_prev_button_clicked':
                lambda *e: self.controller.exaile.queue.prev(),
            'on_stop_button_clicked':
                lambda *e: self.controller.exaile.player.stop(),
            'on_shuffle_button_toggled': self.set_mode_toggles,
            'on_repeat_button_toggled': self.set_mode_toggles,
            'on_dynamic_button_toggled': self.set_mode_toggles,
            'on_clear_playlist_button_clicked': self.on_clear_playlist,
            'on_playlist_notebook_remove': self.on_playlist_notebook_remove,
            'on_new_playlist_item_activated': lambda *e:
                self.add_playlist(),
            'on_volume_slider_value_changed': self.on_volume_changed,
        })        

        event.add_callback(self.on_playback_end, 'playback_end',
            self.player)
        event.add_callback(self.on_playback_start, 'playback_start',
            self.player) 
        event.add_callback(self.on_toggle_pause, 'playback_toggle_pause',
            self.player)
        event.add_callback(self.on_tags_parsed, 'tags_parsed',
            self.player)
        event.add_callback(self.on_buffering, 'playback_buffering',
            self.player)
        event.add_callback(self.on_playback_error, 'playback_error', 
            self.player)

        # monitor the queue
        event.add_callback(lambda *e: self.update_track_counts(),
            'tracks_added', self.queue)
        event.add_callback(lambda *e: self.update_track_counts(),
            'tracks_removed', self.queue)
        event.add_callback(lambda *e:
            self.get_selected_playlist().list.queue_draw, 'stop_track',
            self.queue)

    @guiutil.gtkrun
    def on_playback_error(self, type, player, message):
        """
            Called when there has been a playback error
        """
        commondialogs.error(self.window, message)

    @guiutil.gtkrun
    def on_buffering(self, type, player, percent):
        """
            Called when a stream is buffering
        """
        if percent < 100:
            self.status.set_label("Buffering: %d%%..." % percent, 1000)
        else:
            self.status.set_label("Buffering: 100%...", 1000)

    @guiutil.gtkrun
    def on_tags_parsed(self, type, player, args):
        """
            Called when tags are parsed from a stream/track
        """
        (tr, args) = args
        if tr.is_local(): return
        if track.parse_stream_tags(tr, args):
            self._update_track_information()
            self.cover.on_playback_start('', self.player, None)
            self.get_selected_playlist().refresh_row(tr)

    @guiutil.gtkrun
    def on_toggle_pause(self, type, player, object):
        """
            Called when the user clicks the play button after playback has
            already begun
        """
        if player.is_paused():
            image = gtk.image_new_from_stock('gtk-media-play',
                gtk.ICON_SIZE_SMALL_TOOLBAR)
        else:
            image = gtk.image_new_from_stock('gtk-media-pause',
                gtk.ICON_SIZE_SMALL_TOOLBAR)
            
        self.play_button.set_image(image)
        
        # refresh the current playlist
        pl = self.get_selected_playlist()
        if pl:
            pl.list.queue_draw()

    def close_playlist_tab(self, tab=None):
        """
            Closes the tab specified
            @param tab: the tab number to close.  If no number is specified,
                the currently selected tab is closed
        """
        if tab is None:
            tab = self.playlist_notebook.get_current_page()
        self.playlist_notebook.remove_page(tab)

    def on_playlist_notebook_remove(self, notebook, widget):
        """
            Called when a tab is removed from the playlist notebook
        """
        if notebook.get_n_pages() == 0:
            self.add_playlist()

    def on_clear_playlist(self, *e):
        """
            Clears the current playlist tab
        """
        playlist = self.get_selected_playlist()
        if not playlist: return
        playlist.playlist.clear()

    def set_mode_toggles(self, *e):
        """
            Called when the user clicks one of the playback mode buttons
        """
        self.settings['playback/shuffle'] = self.shuffle_toggle.get_active()
        self.settings['playback/repeat'] = self.repeat_toggle.get_active()
        self.settings['playback/dynamic'] = self.dynamic_toggle.get_active()

        pl = self.get_selected_playlist()
        if pl:
            pl.playlist.set_random(self.shuffle_toggle.get_active())
            pl.playlist.set_repeat(self.repeat_toggle.get_active())

    @guiutil.gtkrun
    def on_playback_start(self, type, player, object):
        """
            Called when playback starts
            Sets the currently playing track visible in the currently selected
            playlist if the user has chosen this setting
        """
        pl = self.get_selected_playlist()
        if player.current in pl.playlist.ordered_tracks:
            path = (pl.playlist.index(player.current),)
        
            if self.settings.get_option('gui/ensure_visible', True):
                pl.list.scroll_to_cell(path)

            gobject.idle_add(pl.list.set_cursor, path)

        self._update_track_information()
        self.draw_playlist(type, player, object)
        self.play_button.set_image(gtk.image_new_from_stock('gtk-media-pause',
                gtk.ICON_SIZE_SMALL_TOOLBAR))
        self.update_track_counts()

        self.rating_combo.set_sensitive(True)
        self.update_rating_combo()
        if self.settings.get_option('playback/dynamic', False):
            self._get_dynamic_tracks()

        if self.settings.get_option('osd/enabled', True):
            self.osd.show(self.player.current)

    @guiutil.gtkrun
    def on_playback_end(self, type, player, object):
        """
            Called when playback ends
        """
        self.track_title_label.set_label(_('Not Playing'))
        self.track_info_label.set_label(_('Stopped'))

        self.draw_playlist(type, player, object)
        self.play_button.set_image(gtk.image_new_from_stock('gtk-media-play',
                gtk.ICON_SIZE_SMALL_TOOLBAR))

        self.rating_combo.set_sensitive(False)
        self.update_rating_combo(0)

    @common.threaded
    def _get_dynamic_tracks(self):
        """
            Gets some dynamic tracks from the dynamic manager.  

            This tries to keep at least 5 tracks the current playlist... if
            there are already 5, it just adds one
        """
        playlist = self.get_selected_playlist()
        if not playlist: return

        if not self.controller.exaile.dynamic.get_providers():
            logger.warning("Dynamic mode is enabled, but there "
                "are no dynamic providers!")
            return

        pl = playlist.playlist

        number = 5 - len(pl)
        if number <= 0: number = 1

        logger.info("Dynamic: attempting to get %d tracks" % number)
        tracks = self.controller.exaile.dynamic.find_similar_tracks(
            self.player.current, number, pl.ordered_tracks)

        logger.info("Dynamic: %d tracks fetched" % len(tracks))

        pl.add_tracks(tracks) 

    def _update_track_information(self):
        """
            Sets track information
        """
        # set track information
        track = self.player.current

        if track:
            artist = track['artist']
            album = track['album']
            title = track['title']
            if title is None: 
                title = ''
            else:
                title = " / ".join(title)
            if album is None: 
                album = ''
            else:
                album = " / ".join(album)
            if artist is None: 
                artist = ''
            else:
                artist = " / ".join(artist)

            if artist:
                # TRANSLATORS: Window title
                self.window.set_title(_("%(title)s (by %(artist)s)" %
                    { 'title': title, 'artist': artist }) + " - Exaile")
            else:
                self.window.set_title(title + " - Exaile")

        self.track_title_label.set_label(title)
        if album or artist:
            desc = []
            # TRANSLATORS: Part of the sentence: "(title) by (artist) from (album)"
            if artist: desc.append(_("by %s") % artist)
            # TRANSLATORS: Part of the sentence: "(title) by (artist) from (album)"
            if album: desc.append(_("from %s") % album)

            #self.window.set_title(_("Exaile: playing %s") % title +
            #    ' ' + ' '.join(desc))
            desc_newline = '\n'.join(desc)
            self.track_info_label.set_label(desc_newline)
            if self.controller.tray_icon:
                self.controller.tray_icon.set_tooltip(_("Playing %s") % title +
                    '\n' + desc_newline)
        else:
            self.window.set_title(_("Exaile: playing %s") % title)
            self.track_info_label.set_label("")
            if self.controller.tray_icon:
                self.controller.tray_icon.set_tooltip(_("Playing %s") % title)

    def draw_playlist(self, *e):
        """
            Called when playback starts, redraws teh playlist
        """
        page = self.playlist_notebook.get_current_page()
        page = self.playlist_notebook.get_nth_page(page)
        gobject.idle_add(page.queue_draw)

    def get_selected_playlist(self):
        """
            Returns teh currently selected playlist
        """
        page = self.playlist_notebook.get_nth_page(self.current_page)
        if page: return page
        num = self.playlist_notebook.get_current_page()
        page = self.playlist_notebook.get_nth_page(num)
        return page

    get_current_playlist = get_selected_playlist

    def on_play_clicked(self, *e):
        """
            Called when the play button is clicked
        """
        exaile = self.controller.exaile
        if exaile.player.is_paused() or exaile.player.is_playing():
            exaile.player.toggle_pause()
        else:
            pl = self.get_selected_playlist()
            exaile.queue.set_current_playlist(pl.playlist)
            if pl:
                track = pl.get_selected_track()
                if track:
                    pl.playlist.set_current_pos(
                        pl.playlist.index(track))
            exaile.queue.play()

    def playlist_switch_event(self, notebook, page, page_num):
        """
            Called when the page is changed in the playlist notebook
        """
        page = notebook.get_nth_page(page_num)
        self.current_page = page_num
        self.set_mode_toggles()
        self.update_track_counts()

    def _setup_position(self):
        """
            Sets up the position and sized based on the size the window was
            when it was last moved or resized
        """
        if self.settings.get_option('gui/mainw_maximized', False):
            self.window.maximize()
            
        width = self.settings.get_option('gui/mainw_width', 500)
        height = self.settings.get_option('gui/mainw_height', 475)
        x = self.settings.get_option('gui/mainw_x', 10)
        y = self.settings.get_option('gui/mainw_y', 10)

        self.window.move(x, y)
        self.window.resize(width, height)

        pos = self.settings.get_option('gui/mainw_sash_pos', 200)
        self.splitter.set_position(pos)

    def delete_event(self, *e):
        """
            Called when the user attempts to close the window
        """
        self.window.hide()
        gobject.idle_add(self.controller.exaile.quit)
        return True

    def configure_event(self, *e):
        """
            Called when the window is resized or moved
        """
        if self.settings.get_option('gui/mainw_maximized', False):
            return False
        (width, height) = self.window.get_size()
        if [width, height] != [ settings.get_option("gui/mainw_"+key, -1) for \
                key in ["width", "height"] ]:
            self.settings['gui/mainw_height'] = height
            self.settings['gui/mainw_width'] = width
        (x, y) = self.window.get_position()
        if [x, y] != [ settings.get_option("gui/mainw_"+key, -1) for \
                key in ["x", "y"] ]:
            self.settings['gui/mainw_x'] = x
            self.settings['gui/mainw_y'] = y
        pos = self.splitter.get_position()
        if pos > 10 and pos != self.settings.get_option("gui/mainw_sash_pos", -1):
            self.settings['gui/mainw_sash_pos'] = pos

        return False

    def window_state_change_event(self, widget, event):
        """
            Saves the current maximized state
        """
        if event.changed_mask & gtk.gdk.WINDOW_STATE_MAXIMIZED:
            self.settings.set_option('gui/mainw_maximized',
                bool(event.new_window_state & gtk.gdk.WINDOW_STATE_MAXIMIZED))
        return False
