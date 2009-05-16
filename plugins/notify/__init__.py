import pynotify, cgi
from xl import event
from xl.nls import gettext as _

pynotify.init('exailenotify')

class ExaileNotification(object):
    def __init__(self):
        self.notification = pynotify.Notification("Exaile")
        self.exaile = None

    def on_play(self, type, player, track):
        title = " / ".join(track['title'] or _("Unknown"))
        artist = " / ".join(track['artist'] or "")
        album = " / ".join(track['album'] or "")
        summary = title
        if artist and album:
            body = _("by %(artist)s\nfrom <i>%(album)s</i>") % {
                'artist' : cgi.escape(artist), 
                'album' : cgi.escape(album)}
        elif artist:
            body = _("by %(artist)s") % {'artist' : cgi.escape(artist)}
        elif album:
            body = _("from %(album)s") % {'album' : cgi.escape(album)}
        else:
            body = ""
        self.notification.update(summary, body)
        item = track.get_album_tuple()
        image = None
        if all(item) and hasattr(self.exaile, 'covers'):
            image = self.exaile.covers.coverdb.get_cover(*item)
        if image is None:
            image = 'exaile'
        self.notification.set_property('icon-name', image)
        self.notification.show()

EXAILE_NOTIFICATION = ExaileNotification()

def enable(exaile):
    EXAILE_NOTIFICATION.exaile = exaile
    event.add_callback(EXAILE_NOTIFICATION.on_play, 'playback_start')

def disable(exaile):
    event.remove_callback(EXAILE_NOTIFICATION.on_play, 'playback_start')
