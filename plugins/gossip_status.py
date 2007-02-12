#!/usr/bin/env python
# encoding=utf-8

# gossip_status - changes Gossip status message according to what you are listening now.
# Copyright (C) 2007 Bryan Forbes <bryan@reigndropsfall.net>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

PLUGIN_NAME = "Gossip Status"
PLUGIN_AUTHORS = ["Bryan Forbes <bryan@reigndropsfall.net>", ]

PLUGIN_VERSION = "0.1"
PLUGIN_DESCRIPTION = "Changes Gossip status message according to what you are listening now."
PLUGIN_ENABLED = False
PLUGIN_ICON = None

import plugins, dbus


CON = plugins.SignalContainer()


def generate_message(track, paused=False):
    message = '♪ "%s" by %s ♪' % (track.title, track.artist)
    if paused:
        message += " [paused]"
    return message


def set_gossip_status(status_message):
    try:
        state, status = INTERFACE.GetPresence("")
    except dbus.DBusException:
        return
    INTERFACE.SetPresence(state, status_message)

def track_information_updated(arg):
    track = APP.player.current
    if PLUGIN_ENABLED and track:
        message = generate_message(track)
        set_gossip_status(message)

def pause_toggle(exaile, track):
    """
        Called when a track stops playing
    """
    if PLUGIN_ENABLED:
        if APP.player.is_paused():
            message = generate_message(track, paused=True)
            set_gossip_status(message)
        else:
            message = generate_message(track)
            set_gossip_status(message)

def initialize():
    """
        Inizializes the plugin
    """
    global SETTINGS, APP, INTERFACE
    exaile = APP
    SETTINGS = exaile.settings

    INTERFACE = dbus.Interface(dbus.SessionBus().get_object('org.gnome.Gossip',
        '/org/gnome/Gossip'),
        'org.gnome.Gossip')

    CON.connect(APP, 'track-information-updated', 
        track_information_updated)
    CON.connect(APP, 'pause-toggled', pause_toggle)

    return True

def destroy():
    """
        Destroys the plugin
    """
    CON.disconnect_all()
