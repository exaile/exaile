import pynotify, cgi
from xl import event
from gettext import gettext as _

pynotify.init('exailenotify')

def on_play(type, player, track):
    title = track['title'] or _("Unknown")
    artist = track['artist']
    album = track['album']
    summary = cgi.escape(title)
    if artist and album:
        body = _("by %s\nfrom <i>%s</i>") % (cgi.escape(artist), 
            cgi.escape(album))
    elif artist:
        body = _("by %s" % (cgi.escape(artist)))
    elif album:
        body = _("from %s" % (cgi.escape(album)))
    else:
        body = ""
    notify = pynotify.Notification(summary, body)

    notify.show()

def enable(exaile):
    event.add_callback(on_play, 'playback_start')

def disable(exaile):
    event.remove_callback(on_play, 'playback_start')
