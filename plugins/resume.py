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
PREFIX = plugins.name(__file__) + "_"
PLAYING = PREFIX + "playing"
TRACK = PREFIX + "track"
PROGRESS = PREFIX + "progress"

def restore_state():
    """
    Tries to restore the saved state form the settings
    """
    while gtk.events_pending():
        gtk.main_iteration()
    if APP.settings.get_boolean(PLAYING, False):
        if APP.tracks:
            songs = APP.tracks.get_songs()
            track = APP.settings.get_int(TRACK)
            if track < len(songs):
                APP.player.play_track(songs[track])
                APP.player.current = songs[track]
                APP.player.seek(APP.settings.get_float(PROGRESS,0.1))
                APP.tracks.queue_draw()
            elif len(songs) == 0:
                return True
    

def save_state(sender):
    """
    save the current song and playback status to the config
    """
    track = APP.player.current
    if track:
        APP.settings[PLAYING] = APP.player.is_playing()
        if APP.tracks:
            songs = APP.tracks.get_songs()
            if songs:
                APP.settings[TRACK] = songs.index(track)
                APP.settings[PROGRESS] = APP.player.get_current_position() * track.duration /\
                        100.0
    else:
        APP.settings[PLAYING] = False
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
