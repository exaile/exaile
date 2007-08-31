#!/usr/bin/env python
import gtk, gobject, time
import xl.plugins as plugins

PLUGIN_NAME = "Resume Playback"
PLUGIN_AUTHORS = ['Jonas Wagner <veers' + chr(32+32) + 'gmx' + '.ch>']
PLUGIN_VERSION = "0.2.2"
PLUGIN_DESCRIPTION = r"""Resumes playback after restarting exaile"""

PLUGIN_ENABLED = False
PLUGIN_ICON = None
PLUGIN = None
SETTINGS = None
TIMER_ID = None
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
        loc = APP.settings.get_str(TRACK, plugin=PLUGIN_NAME)
        track = APP.all_songs.for_path(loc)
        
        if not track: return
        track.submitted = True
        APP.player.play_track(track)
        APP.player.current = track
        APP.player.seek(APP.settings.get_float(PROGRESS, default=0.1, plugin=PLUGIN_NAME))

def save_state(sender):
    """
    save the current song and playback status to the config
    """
    track = APP.player.current
    if track:
        APP.settings.set_boolean(PLAYING, APP.player.is_playing(), plugin=PLUGIN_NAME)
        APP.settings.set_str(TRACK, track.io_loc, plugin=PLUGIN_NAME)
        APP.settings.set_float(PROGRESS, APP.player.get_current_position() * track.duration /\
                100.0, plugin=PLUGIN_NAME)
    else:
        APP.settings.set_boolean(PLAYING, False, plugin=PLUGIN_NAME)

def initialize():
    """
    Connect to the PluginEvents
    """
    APP.connect("quit", save_state)
    APP.playlist_manager.connect("last-playlist-loaded", 
            lambda sender: gobject.idle_add(restore_state))
    return True

def destroy():
    """
    Do nothing    
    """
    pass
