#!/usr/bin/env python
import gtk, plugins, gobject, time

PLUGIN_NAME = "Resume Playback"
PLUGIN_AUTHORS = ['Jonas Wagner <veers' + chr(32+32) + 'gmx' + '.ch>']
PLUGIN_VERSION = "0.1"
PLUGIN_DESCRIPTION = r"""Resumes playback after restarting exaile"""

PLUGIN_ENABLED = False
PLUGIN_ICON = None
PLUGIN = None
SETTINGS = None
TIMER_ID = None
PLUGIN_NAME = plugins.name(__file__)
PLAYING = "playing"
TRACK = "track"
PROGRESS = "progress"

def restore_state():
    """
    Tries to restore the saved state form the settings
    """
    while gtk.events_pending():
        gtk.main_iteration()
    if APP.settings.get_boolean(PLAYING, default=False, plugin=PLUGIN_NAME):
        if APP.tracks:
            songs = APP.tracks.get_songs()
            track = APP.settings.get_int(TRACK, plugin=PLUGIN_NAME)
            
            if track < len(songs):
                songs[track].submitted = True
                APP.player.play_track(songs[track])
                APP.player.current = songs[track]
                APP.player.seek(APP.settings.get_float(PROGRESS, default=0.1, plugin=PLUGIN_NAME))
            elif len(songs) == 0:
                return True
    

def save_state(sender):
    """
    save the current song and playback status to the config
    """
    track = APP.player.current
    if track:
        APP.settings.set_boolean(PLAYING, APP.player.is_playing(), plugin=PLUGIN_NAME)
        if APP.tracks:
            songs = APP.tracks.get_songs()
            if songs:
                APP.settings.set_int(TRACK, songs.index(track), plugin=PLUGIN_NAME)
                APP.settings.set_float(PROGRESS, APP.player.get_current_position() * track.duration /\
                        100.0, plugin=PLUGIN_NAME)
    else:
        APP.settings.set_boolean(PLAYING, False, plugin=PLUGIN_NAME)
    APP.settings.save()

def initialize():
    """
    Connect to the PluginEvents
    """
    APP.connect("quit", save_state)
    APP.connect("last-playlist-loaded", 
            lambda sender: gobject.idle_add(restore_state))
    return True

def destroy():
    """
    Do nothing    
    """
    pass
