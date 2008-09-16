import pynotify, cgi
from xl import event
from gettext import gettext as _

pynotify.init('exailenotify')

def on_play(type, player, track):
    title = " / ".join(track['title'] or _("Unknown"))
    artist = " / ".join(track['artist'] or "")
    album = " / ".join(track['album'] or "")
    summary = cgi.escape(title)
    if artist and album:
        body = _("by %(artist)s\nfrom <i>%(album)s</i>") % {
            'artist' : cgi.escape(artist), 
            'album' : cgi.escape(album)}
    elif artist:
        body = _("by %(artist)s" % {'artist' : cgi.escape(artist)})
    elif album:
        body = _("from %(album)s" % {'album' : cgi.escape(album)})
    else:
        body = ""
    notify = pynotify.Notification(summary, body)

    notify.show()

def enable(exaile):
    event.add_callback(on_play, 'playback_start')

def disable(exaile):
    event.remove_callback(on_play, 'playback_start')
