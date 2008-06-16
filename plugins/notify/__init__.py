import pynotify, cgi
from xl import event

pynotify.init('exailenotify')

def on_play(type, player, track):
    summary = cgi.escape(track['title'])
    body = "%s\non <i>%s</i>" % (cgi.escape(track['artist']), 
        cgi.escape(track['album']))
    notify = pynotify.Notification(summary, body)

    notify.show()

def enable(exaile):
    event.add_callback(on_play, 'playback_start')

def disable(exaile):
    event.remove_callback(on_play, 'playback_start')
