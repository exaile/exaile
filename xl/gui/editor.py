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

import os, threading, re
from xl import media, library, common
from gettext import gettext as _, ngettext
import gtk, gtk.glade
import playlist as trackslist

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
        self.action_area = self.xml.get_widget('track_editor_action_area')

        self.tracks = tracks
        self.songs = tracks.get_selected_tracks()
        track = self.songs[0]
        self.count = len(self.songs)
        self.get_widgets()


        self.artist_entry.set_text(track.artist)
        self.album_entry.set_text(track.album)
        self.genre_entry.set_text(track.genre)
        self.year_entry.set_text(track.year)
        self.disc_id_entry.set_text(str(track.disc_id))

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
        self.save.connect('clicked', self.on_save)

        self.dialog.show()

    def get_widgets(self):
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
        self.disc_id_entry = xml.get_widget('te_disc_id_entry')
        self.cancel = xml.get_widget('te_cancel_button')
        self.save = xml.get_widget('te_save_button')

    def on_save(self, widget):
        """
            Writes the information to the tracks.  Called when the user clicks
            save
        """
        errors = []
        for track in self.songs:
            xlmisc.finish()

            if track.type == 'stream' or track.type == 'cd':
                errors.append("Could not write track %s" % track.loc)
                continue

            if self.count == 1:
                track.title = self.title_entry.get_text()
                track.track = self.track_entry.get_text()

            track.artist = self.artist_entry.get_text()
            
            track.album = self.album_entry.get_text()
            track.genre = self.genre_entry.get_text()
            track.year = self.year_entry.get_text()
            track.disc_id = self.disc_id_entry.get_text()
            try:
                db = self.exaile.db
                media.write_tag(track)
                library.save_track_to_db(db, track)
                self.exaile.tracks.refresh_row(track)
            except:
                errors.append("Unknown error writing tag for %s" % track.loc)
                xlmisc.log_exception()

        self.exaile.tracks.queue_draw()

        self.exaile.db.db.commit()
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

def edit_field(caller, data):
    """
        Edits one field in a list of tracks
    """
    songs = caller.get_selected_tracks()
    if not songs: return
    text = getattr(songs[0], data)

    dialog = common.TextEntryDialog(
        caller.exaile.window, 
        ngettext("Enter the %s for the selected track",
            "Enter the %s for the selected tracks", len(songs)) %
            _(data.capitalize()),
        _("Edit %s") % _(data.capitalize()))
    dialog.set_value(text)

    if dialog.run() == gtk.RESPONSE_OK:
        value = dialog.get_value()
        errors = ''
        for song in songs:
            setattr(song, data, value)
            try:
                media.write_tag(song)    
                library.save_track_to_db(caller.db, song)
            except:
                errors += "Could not write tag for %s\n" % song.loc
                xlmisc.log_exception()

            xlmisc.finish()
            if isinstance(caller, trackslist.TracksListCtrl):
                caller.refresh_row(song)

        if errors:
            common.scrolledMessageDialog(caller.exaile.window,
                errors, "Error writing tags")                    
        
    dialog.destroy()

def update_rating(caller, num):
    """
        Updates the rating based on which menu id was clicked
    """
    rating = num + 1

    cur = caller.db.cursor()
    for track in caller.get_selected_tracks():
        
        path_id = library.get_column_id(caller.db, 'paths', 'name',
            track.loc)
        caller.db.execute("UPDATE tracks SET user_rating=? WHERE path=?",
            (rating, path_id)) 
        track.rating = rating
        if isinstance(caller, trackslist.TracksListCtrl):
            caller.refresh_row(track)
