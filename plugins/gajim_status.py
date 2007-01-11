#!/usr/bin/env python
# encoding=utf-8

# gajim_status - changes Gajim status message according to what you are listening now.
# Copyright (C) 2006 Andrey Fedoseev <andrey.fedoseev@gmail.com>
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

PLUGIN_NAME = "Gajim Status"
PLUGIN_AUTHORS = ["Andrey Fedoseev <andrey.fedoseev@gmail.com>", ]

PLUGIN_VERSION = "0.1"
PLUGIN_DESCRIPTION = "Changes Gajim status message according to what you are listening now."
PLUGIN_ENABLED = False
PLUGIN_ICON = None

import plugins, dbus


CON = plugins.SignalContainer()


def generate_message(track, paused=False):
    message = '♪ "%s" by %s ♪' % (track.title, track.artist)
    if paused:
        message += " [paused]"
    return message


def set_gajim_status(message):
    status = INTERFACE.get_status()
    INTERFACE.change_status(status, message)

def track_information_updated(arg):
    track = APP.current_track
    if PLUGIN_ENABLED and track:
        message = generate_message(track)
        set_gajim_status(message)

def pause_toggle(exaile, track):
    """
        Called when a track stops playing
    """
    if PLUGIN_ENABLED:
        if track.is_paused():
            message = generate_message(track, paused=True)
            set_gajim_status(message)
        else:
            message = generate_message(track)
            set_gajim_status(message)

def initialize():
    """
        Inizializes the plugin
    """
    global SETTINGS, APP, INTERFACE
    exaile = APP
    SETTINGS = exaile.settings

    INTERFACE = dbus.Interface(dbus.SessionBus().get_object('org.gajim.dbus',
        '/org/gajim/dbus/RemoteObject'),
        'org.gajim.dbus.RemoteInterface')

    CON.connect(APP, 'track-information-updated', 
        track_information_updated)
    CON.connect(APP, 'pause-toggled', pause_toggle)

    return True

def destroy():
    """
        Destroys the plugin
    """
    CON.disconnect_all()
