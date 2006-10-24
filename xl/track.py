# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

import os, threading, httplib, xlmisc, md5, re, common
import media, gc
from urllib import urlencode
from gettext import gettext as _

import pygtk
pygtk.require('2.0')
import gtk, gtk.glade, pango

def update_info(nb, track):
    """
        Changes the information in the info tab if it's already open
    """
    for i in range(0, nb.get_n_pages()):
        page = nb.get_nth_page(i)
        if isinstance(page, TrackInformation):
            page.setup_tabs(track)

def show_information(exaile, track):
    """
        Shows track information
    """
    nb = exaile.playlists_nb
    for i in range(0, nb.get_n_pages()):
        page = nb.get_nth_page(i)
        if isinstance(page, TrackInformation):
            page.setup_tabs(track)
            page.set_current_page(i)
            return page

    return TrackInformation(exaile, track)

class TablatureTab(gtk.VBox):
    """
        Downloads and displays guitar tablature
    """
    REGEX = re.compile("<PRE>(.*)</PRE>", re.DOTALL)
    def __init__(self, panel, track):
        """
            Initializes the panel
        """
        gtk.VBox.__init__(self)
        self.set_border_width(5)
        self.set_spacing(3)
        self.exaile = panel.exaile
        self.panel = panel
        self.stopped = False

        text = gtk.TextView()
        text.set_editable(False)

        text.modify_font(pango.FontDescription("Monospace 11"))
        self.text = text.get_buffer()

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.add(text)

        self.text.set_text("Downloading tablature...")
        self.fetched = False
        self.pack_start(scroll, True, True)
        
        self.track = track
        self.artist = track.artist.replace(" ", "_").lower()
        self.letter = self.artist[:1]
        self.title = track.title.replace(" ", "_").lower()
        self.url = "http://www.fretplay.com/tabs/%s/%s/%s-tab.shtml" % \
            (self.letter, self.artist, self.title)
        self.cache_file = "%s/cache/tablature_%s.tablature" % \
            (self.exaile.get_settings_dir(),
            md5.new(self.url).hexdigest())
        if os.path.isfile(self.cache_file):
            h = open(self.cache_file, 'r')
            self.fetched = True
            self.text.set_text(h.read())
            h.close()
        self.update()
        self.show_all()

    def update(self):       
        """
            Called when this tab is selected
        """
        if self.fetched: return
        else:
            self.fetched = False
            xlmisc.log(self.url)
            xlmisc.URLFetcher("www.fretplay.com", "/tabs/%s/%s/%s-tab.shtml" % \
                (self.letter, self.artist, self.title), self.updated).start()

    def updated(self, url, text):
        """
            Called when the text has been fetched.
        """
        if self.track != self.panel.track or \
            self.stopped: return
        m = self.REGEX.search(text)
        if m:
            text = m.group(1)
            text = re.sub("^\s*", "", text)
        else:
            self.text.set_text("Could not fetch tablature.")
        if text.find("Error 302") > -1:
            text = "Tablature not found."
        xlmisc.log(self.cache_file)
        if self.track != self.panel.track or \
            self.stopped: return
        self.text.set_text(text)
        h = open(self.cache_file, 'w')
        h.write(text)
        h.close()            

    def close_page(self):   
        """
            Called when this tab is closed
        """
        self.stopped = True

class LyricsTab(gtk.VBox):
    """
        Downloads and displays track lyrics
    """
    def __init__(self, exaile, panel, track):
        """
            Initializes the panel
        """
        gtk.VBox.__init__(self)
        self.set_border_width(5)
        self.set_spacing(3)
        self.exaile = exaile
        self.panel = panel
        self.track = track
        self.text = xlmisc.BrowserWindow(exaile, None, True) 
        self.pack_start(self.text, True, True)

        self.show_all()
        self.lyrics = self.text
        self.lyrics.set_text("Downloading lyrics, please wait...") 
        self.update()

    def update(self):
        """
            Called when this tab is selected
        """
        params = {'artist': self.track.artist, 'songname': self.track.title}

        search = "http://lyrc.com.ar/en/tema1en.php?%s" % urlencode(params)
        print search
        self.lyrics.t = xlmisc.ThreadRunner(self.lyrics.load_url)
        self.lyrics.t.history = False
        self.lyrics.t.action_count = self.text.action_count
        self.lyrics.t.url = search
        self.lyrics.t.start()

    def close_page(self):
        """
            Called when this tab is closed
        """
        self.text.stopped = True

class WikipediaTab(gtk.HBox):
    """
        Shows a wikipedia page
    """
    def __init__(self, exaile, url):
        """
            Initializes the panel
        """
        gtk.HBox.__init__(self)
        self.browser = xlmisc.BrowserWindow(exaile, url)
        self.pack_start(self.browser, True, True)
        self.show_all()

    def close_page(self):
        """
            called when this tab is closed
        """
        self.browser.stopped = True

class TrackStatsTab(gtk.HBox):
    """
        Track Statistics
    """
    def __init__(self, exaile, track):
        """
            Initializes the tab
        """
        gtk.HBox.__init__(self)
        self.set_border_width(5)
        self.db = exaile.db

        self.left = gtk.VBox()
        self.left.set_spacing(3)
        self.pack_start(self.left, False, False)
        self.right = gtk.VBox()
        self.right.set_spacing(3)
        self.pack_start(self.right, True, False)
        self.setup_information(track)

        self.show_all()

    def setup_information(self, track):
        """
            Adds the specific information fields for this track
        """
        row = self.db.read_one("tracks", "plays, rating", "path=?", (track.loc,))

        playcount = 0
        rating = 0
        if row:
            playcount = row[0]
            rating = row[1]
        self.append_info(_("Title: "), track.title)
        self.append_info(_("Artist:" ), track.artist)
        self.append_info(_("Album:"), track.album)
        if track.track and track.track > -1: 
            self.append_info(_("Track Number:"), str(track.track))
        self.append_info(_("Year:"), track.year)
        self.append_info(_("Genre:"), track.genre)
        self.append_info(_("Bitrate:"), str(track.bitrate))
        if track.rating: self.append_info(_("User Rating:"), track.rating)
        self.append_info(_("System Rating:"), str(rating))
        if playcount >= 0: self.append_info(_("Playcount:"), str(playcount))
        self.append_info(_("Location: "), track.loc)

    def append_info(self, label, string):
        """
            Appends an information line
        """
        label = gtk.Label(label)
        label.set_alignment(0, 0)
        attr = pango.AttrList()
        attr.change(pango.AttrWeight(pango.WEIGHT_BOLD, 0, 800))
        label.set_attributes(attr)

        self.left.pack_start(label, False, False)

        if isinstance(string, unicode) or isinstance(string, str):
            label = gtk.Label(string)
            label.set_alignment(0, 0)
            label.set_line_wrap(True)
            self.right.pack_start(label, False, False)
        else:
            self.right.pack_start(string, False, True)

    def close_page(self):
        """
            Called when this tab is closed
        """
        pass

class RadioTrackStatsTab(TrackStatsTab):
    """
        Track statistic for shoutcase streams
    """
    def __init__(self, exaile, track):
        TrackStatsTab.__init__(self, exaile, track)

    def setup_information(self, track):
        """
            Sets up the specific information fields for this track
        """

        self.append_info(_("Title: "), track.title)
        self.append_info(_("Description: "), track.artist)

        location = gtk.Entry()
        location.set_text(track.loc)
        location.set_editable(False)
        self.append_info(_("Location: "), location)
        self.append_info(_("Bitrate: "), track.bitrate)

class TrackInformation(gtk.Notebook):
    """
        Shows information regarding a track
    """
    def __init__(self, exaile, track):
        """
            Initializes the track information page
        """
        gtk.Notebook.__init__(self)
        self.exaile = exaile
        self.db = exaile.db

        self.setup_tabs(track)
        self.show_all()

        self.exaile.playlists_nb.append_page(self, xlmisc.NotebookTab(exaile,
            _("Information"), self))
        self.exaile.playlists_nb.set_current_page(
            self.exaile.playlists_nb.get_n_pages() - 1)

    def setup_tabs(self, track):
        """
            Sets up the tabs for the specified track
        """
        self.track = track
        for i in range(0, self.get_n_pages()):
            self.remove_page(0)

        if isinstance(track, media.RadioTrack): 
            self.append_page(RadioTrackStatsTab(self.exaile, track),
                gtk.Label(_("Statistics")))
        else:
            self.append_page(TrackStatsTab(self.exaile, track), gtk.Label(_("Statistics")))
            locale = self.exaile.settings.get('wikipedia_locale', 'en')

            if xlmisc.GNOME_EXTRAS_AVAIL:
                artist = "http://%s.wikipedia.org/wiki/%s" % (locale, track.artist)
                artist = artist.replace(" ", "_")
                self.append_page(WikipediaTab(self.exaile, artist),
                    gtk.Label(_("Artist")))
                album = "http://%s.wikipedia.org/wiki/%s" % (locale, track.album)
                album = album.replace(" ", "_")
                self.append_page(WikipediaTab(self.exaile, album),
                    gtk.Label(_("Album")))
            else:
                xlmisc.log("gnome-extras not available.  Not showing artist or"
                    " album information")
            self.append_page(LyricsTab(self.exaile, self, track),
                gtk.Label(_("Lyrics")))
            self.append_page(TablatureTab(self, track),
                gtk.Label(_("Tablature")))
        self.show_all()

    def close_page(self):
        """
            Called when this tab in the notebook is closed
        """
        for i in range(self.get_n_pages()):
            page = self.get_nth_page(i)
            page.close_page()

        self.destroy()
        gc.collect()

class TrackEditor(object):
    """
        A track properties editor
    """
    def __init__(self, exaile, tracks):
        """
            Inizializes the panel 
        """
        self.exaile = exaile
        self.db = exaile.db
        self.xml = gtk.glade.XML('exaile.glade', 'TrackEditorDialog', 'exaile')
        self.dialog = self.xml.get_widget('TrackEditorDialog')
        self.dialog.set_transient_for(self.exaile.window)

        self.tracks = tracks
        self.songs = tracks.get_selected_tracks()
        track = self.songs[0]
        self.count = len(self.songs)
        self.__get_widgets()


        self.artist_entry.set_text(track.artist)
        self.album_entry.set_text(track.album)
        self.genre_entry.set_text(track.genre)
        self.year_entry.set_text(track.year)

        if self.count > 1:
            self.title_entry.hide()
            self.track_entry.hide()
            self.title_label.hide()
            self.track_label.hide()
        else:
            num = track.track
            if num == -1: num = ''
            self.title_entry.set_text(track.title)
            self.track_entry.set_text(str(num))

        self.cancel.connect('clicked', lambda e: self.dialog.destroy())
        self.save.connect('clicked', self.__save)

        self.dialog.show()

    def __get_widgets(self):
        """
            Gets all widgets from the glade definition file
        """
        xml = self.xml
        self.title_label = xml.get_widget('te_title_label')
        self.title_entry = xml.get_widget('te_title_entry')

        self.artist_entry = xml.get_widget('te_artist_entry')
        self.album_entry = xml.get_widget('te_album_entry')
        self.genre_entry = xml.get_widget('te_genre_entry')
        self.year_entry = xml.get_widget('te_year_entry')
        self.track_label = xml.get_widget('te_track_label')
        self.track_entry = xml.get_widget('te_track_entry')
        self.cancel = xml.get_widget('te_cancel_button')
        self.save = xml.get_widget('te_save_button')

    def __save(self, widget):
        """
            Writes the information to the tracks.  Called when the user clicks
            save
        """
        errors = []
        ipod = False
        for track in self.songs:
            xlmisc.finish()

            if track.type == 'stream' or track.type == 'cd':
                errors.append("Could not write track %s" % track.loc)
                continue

            if isinstance(track, media.iPodTrack): ipod = True
            if self.count == 1:
                track.title = self.title_entry.get_text()
                track.track = self.track_entry.get_text()

            track.artist = self.artist_entry.get_text()
            
            # find out if it's a "the" track
            if track.artist.lower()[:4] == "the ":
                track.the_track = track.artist[4:]
                track.artist = track.artist[:4]

            track.album = self.album_entry.get_text()
            track.genre = self.genre_entry.get_text()
            track.year = self.year_entry.get_text()
            try:
                db = self.exaile.db
                if isinstance(track, media.iPodTrack):
                    db = self.exaile.ipod_panel.db
                track.write_tag(db)
            except media.MetaIOException, ex:
                errors.append(ex.reason)
            except:
                errors.append("Unknown error writing tag for %s" % track.loc)
                xlmisc.log_exception()

        if errors:
            message = ""
            count = 1
            for error in errors:
                message += "%d: %s\n" % (count, error)
                count += 1
            self.dialog.hide()
            common.scrolledMessageDialog(self.exaile.window, message, _("Some errors"
                " occurred"))    
        else:
            self.dialog.destroy()

        if ipod:
            self.exaile.ipod_panel.save_database()
        self.exaile.tracks.set_songs(self.tracks.songs)
