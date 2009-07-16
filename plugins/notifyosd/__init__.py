# Copyright (C) 2009
#	Adam Olsen <arolsen@gmail.com>
#	Abhishek Mukherjee <abhishek.mukher.g@gmail.com>
#	Steve Dodier <sidnioulzg@gmail.com>
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
import pynotify, cgi
import logging
import notifyosd_cover
from xl import event
from xl.nls import gettext as _

logger = logging.getLogger(__name__)
pynotify.init('Exaile')

class ExaileNotifyOsd(object):

    def __init__(self):
        self.notify = pynotify.Notification('Exaile')
        self.exaile = None
        self.body = None
        self.summary = None
        self.cover = None
        self.pauseicon = 'notification-audio-pause'
        self.resumeicon = 'notification-audio-play'
        self.stopicon = 'notification-audio-stop'

#        self.pauseicon = 'gtk-media-pause'
#        self.resumeicon = 'gtk-media-play-ltr'
#        self.stopicon = 'gtk-media-stop'


    def update_track_notify(self, type, player, track, icon = None):
        title = " / ".join(track['title'] or "")
        if title == "":
        	title = _("Unknown")
        artist = " / ".join(track['artist'] or "")
        album = " / ".join(track['album'] or "")
        
        if icon :
            self.cover = icon
        else :
            if self.cover == self.stopicon and self.summary == title:
                # this is for when the song has been stopped previously
                self.cover = self.resumeicon
            else :
                self.cover = notifyosd_cover.notifyosd_get_image_for_track(track, self.exaile)
        
        self.summary = title
        if artist and album:
            self.body = _("%(artist)s\n%(album)s") % {
                'artist' : artist, 
                'album' : album}
        elif artist:
            self.body = _("%(artist)s") % {'artist' : artist}
        elif album:
            self.body = _("%(album)s") % {'album' : album}
        else:
            self.body = ""
        
        if self.cover :
            self.notify.update(self.summary, self.body, self.cover)
        else :
            self.notify.update(self.summary, self.body)
        
        if not self.exaile.gui.main.window.is_active() :
            self.notify.show()
        
    def on_pause(self, type, player, track):
        self.update_track_notify(type, player, track, self.pauseicon)
        
    def on_stop(self, type, player, track):
        self.update_track_notify(type, player, track, self.stopicon)
        
    def on_resume(self, type, player, track):
        self.update_track_notify(type, player, track, self.resumeicon)

    def on_play(self, type, player, track):
        self.update_track_notify(type, player, track)

    def on_quit(self, type, exaile, data=None):
        self.notify.close()


EXAILE_NOTIFYOSD = ExaileNotifyOsd()

def enable(exaile):
    EXAILE_NOTIFYOSD.exaile = exaile
    event.add_callback(EXAILE_NOTIFYOSD.on_play, 'playback_player_start')
    event.add_callback(EXAILE_NOTIFYOSD.on_pause, 'playback_player_pause')
    event.add_callback(EXAILE_NOTIFYOSD.on_stop, 'playback_player_end')
    event.add_callback(EXAILE_NOTIFYOSD.on_resume, 'playback_player_resume')
    event.add_callback(EXAILE_NOTIFYOSD.on_quit, 'quit_application')

def disable(exaile):
    event.remove_callback(EXAILE_NOTIFYOSD.on_play, 'playback_player_start')
    event.remove_callback(EXAILE_NOTIFYOSD.on_pause, 'playback_player_pause')
    event.remove_callback(EXAILE_NOTIFYOSD.on_stop, 'playback_player_end')
    event.remove_callback(EXAILE_NOTIFYOSD.on_resume, 'playback_player_resume')
    event.remove_callback(EXAILE_NOTIFYOSD.on_quit, 'quit_application')
