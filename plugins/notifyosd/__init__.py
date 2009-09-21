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
import pynotify, cgi, gobject, logging
import notifyosd_cover, notifyosdprefs
from xl import event, settings
from xl.nls import gettext as _
import gtk.gdk

logger = logging.getLogger(__name__)
pynotify.init('Exaile')

class ExaileNotifyOsd(object):

    def __inner_preference(klass):
        """Function will make a property for a given subclass of PrefsItem"""
        def getter(self):
            return settings.get_option(klass.name, klass.default or None)

        def setter(self, val):
            settings.set_option(klass.name, val)

        return property(getter, setter)

    show_covers     = __inner_preference(notifyosdprefs.ShowCovers)
    notify_play     = __inner_preference(notifyosdprefs.NotifyPlay)
    notify_pause    = __inner_preference(notifyosdprefs.NotifyPause)
    use_media_icons = __inner_preference(notifyosdprefs.UseMediaIcons)
    tray_hover      = __inner_preference(notifyosdprefs.TrayHover)
    format_summary  = __inner_preference(notifyosdprefs.Summary)
    format_artist   = __inner_preference(notifyosdprefs.BodyArtist)
    format_album    = __inner_preference(notifyosdprefs.BodyAlbum)

    def __init__(self):
        self.notify         = pynotify.Notification('Exaile')
        self.exaile         = None
        self.cover          = None
        self.pauseicon      = 'notification-audio-pause'
        self.resumeicon     = 'notification-audio-play'
        self.stopicon       = 'notification-audio-stop'
        # TRANSLATORS : this replaces the title of a track when it's not known
        self.unknown        = _('Unknown')
        self.summary        = None
        self.body           = None
        self.gui_callback   = False
        self.tray_connection= -1
        event.add_callback(self.on_tray_toggled, 'tray_icon_toggled')

    def update_track_notify(self, type, player, track, media_icon = None):
        # Get the title, artist and album values
        title = " / ".join(track['title'] or "")
        if title == "":
        	title = _("Unknown")
        artist = " / ".join(track['artist'] or "")
        album = " / ".join(track['album'] or "")
        
        # Find the icon we will use
        icon_allowed = False
        if media_icon and self.use_media_icons:
            self.cover = media_icon
            icon_allowed = True
        else:
            if self.cover == self.stopicon and self.summary == title and self.use_media_icons and self.notify_pause:
                # this is for when the song has been stopped previously
                self.cover = self.resumeicon
                icon_allowed = True
            elif self.show_covers:
                self.cover = notifyosd_cover.notifyosd_get_image_for_track(
                    track, self.exaile)
                icon_allowed = True
        
        # Setup the summary and body for the notification
        self.summary = self.format_summary % {'title': title or self.unknown}
        
        if artist and album:
            self.body = self.format_artist % {'artist' : artist} + '\n' + self.format_album % {'album' : album}
        elif artist:
            self.body = self.format_artist % {'artist' : artist}
        elif album:
            self.body = self.format_album % {'album' : album}
        else:
            self.body = ""
        
        if icon_allowed :
            self.notify.update(self.summary, self.body, self.cover)
        else :
            self.notify.update(self.summary, self.body)
        
        if settings.get_option("plugin/notifyosd/show_when_focused", True) or \
                not self.exaile.gui.main.window.is_active():
            self.notify.show()
        
    def on_pause(self, type, player, track):
        if self.notify_pause:
            self.update_track_notify(type, player, track, self.pauseicon)
        
    def on_stop(self, type, player, track):
        if self.notify_pause:
            self.update_track_notify(type, player, track, self.stopicon)
        
    def on_resume(self, type, player, track):
        if self.notify_pause:
            self.update_track_notify(type, player, track, self.resumeicon)
        elif self.notify_play:
            self.update_track_notify(type, player, track)

    def on_play(self, type, player, track):
        if self.notify_play:
            self.update_track_notify(type, player, track)

    def on_quit(self, type, exaile, data=None):
        self.notify.close()
    
    def on_tooltip(self, *e):
        if self.tray_hover:
            track = self.exaile.player.current
            if track:
                if self.cover == self.stopicon or self.cover == self.pauseicon:
                    if self.use_media_icons:
                        self.update_track_notify(type, self.exaile.player, track, self.cover)
                        return
                self.update_track_notify(type, self.exaile.player, track)
            elif self.notify_pause and self.cover == self.stopicon: # if there is no track, then status is stopped
                if self.use_media_icons:
                    self.notify.update(self.summary, self.body, self.cover)
                else:
                    self.notify.update(self.summary, self.body)
                self.notify.show()
                
    
    def exaile_ready(self, type = None, data1 = None, data2 = None):
        if self.exaile.gui.tray_icon:
            self.tray_connection = self.exaile.gui.tray_icon.connect('query-tooltip', self.on_tooltip)
            
    def on_tray_toggled(self, type, object, data):
        if data and self.tray_connection == -1:
            gobject.timeout_add(800, self.exaile_ready)
        elif not data and self.tray_connection != -1:
            self.tray_connection = -1

EXAILE_NOTIFYOSD = ExaileNotifyOsd()

def enable(exaile):
    EXAILE_NOTIFYOSD.exaile = exaile
    event.add_callback(EXAILE_NOTIFYOSD.on_play, 'playback_player_start')
    event.add_callback(EXAILE_NOTIFYOSD.on_pause, 'playback_player_pause')
    event.add_callback(EXAILE_NOTIFYOSD.on_stop, 'playback_player_end')
    event.add_callback(EXAILE_NOTIFYOSD.on_resume, 'playback_player_resume')
    event.add_callback(EXAILE_NOTIFYOSD.on_quit, 'quit_application')
    if hasattr(exaile, 'gui'):
        EXAILE_NOTIFYOSD.exaile_ready()
    else:
        event.add_callback(EXAILE_NOTIFYOSD.exaile_ready, 'gui_loaded')
        EXAILE_NOTIFYOSD.gui_callback = True

def disable(exaile):
    event.remove_callback(EXAILE_NOTIFYOSD.on_play, 'playback_player_start')
    event.remove_callback(EXAILE_NOTIFYOSD.on_pause, 'playback_player_pause')
    event.remove_callback(EXAILE_NOTIFYOSD.on_stop, 'playback_player_end')
    event.remove_callback(EXAILE_NOTIFYOSD.on_resume, 'playback_player_resume')
    event.remove_callback(EXAILE_NOTIFYOSD.on_quit, 'quit_application')
    if EXAILE_NOTIFYOSD.exaile.gui.tray_icon:
        EXAILE_NOTIFYOSD.exaile.gui.tray_icon.icon.disconnect(EXAILE_NOTIFYOSD.tray_connection)
    if EXAILE_NOTIFYOSD.gui_callback:
        event.remove_callback(EXAILE_NOTIFYOSD.exaile_ready, 'gui_loaded')

def get_prefs_pane():
    return notifyosdprefs
