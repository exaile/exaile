#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Code based on Ingelrest FranÃ§ois' "im status" plugin

import dbus, gobject, gtk, os
from gettext import gettext as _
import xl.plugins as plugins

import sys

# Plugin description
PLUGIN_NAME        = _('Current song')
PLUGIN_ICON        = None
PLUGIN_ENABLED     = False
PLUGIN_AUTHORS     = ['Jorge VillaseÃ±or <salinasv@gmail.com']
PLUGIN_VERSION     = '0.1'
PLUGIN_DESCRIPTION = _(r"""Set the current playing song in the Pidgin im client using the tune status (only the supported prpl)""")

# Constants
DEFAULT_UPDATE_ON_PAUSE = True

# Global Variables
mHandlers    = plugins.SignalContainer()
mCurrentTitle = ''

##############################################################################

class Pidgin :

    def __init__(self, dbusInterface) :
        """
            Constructor
        """
        self.purple = dbusInterface

    def listAccounts(self) :
        """
            Purple merges all accounts, so we return a default one
            Each account is associated with:
                * A boolean -> True if the status of this account was changed on the previous track change
        """
        return {'GenericAccount' : False}
    
    def setStatus(self, status, attr, value):
        # this doesn't actually work, for some reason the getter always return ""
        if self.purple.PurpleStatusGetAttrString(status, attr) != value:
            self.purple.PurpleStatusSetAttrString(status, attr, value)
            return True
        return False

    def setTune(self, artist, title, album) :
        """
            Change the tune status
            Return True if the message is successfully updated
        """
        current = self.purple.PurpleSavedstatusGetCurrent()
        accounts = self.purple.PurpleAccountsGetAll()

        for account in accounts:
            if self.purple.PurpleAccountIsConnected(account) != True:
                continue
            p = self.purple.PurpleAccountGetPresence(account)
            status = self.purple.PurplePresenceGetStatus(p, "tune")

            if status != 0:
                updated = False
                if len(title) + len(artist) + len(album) == 0:
                    if self.purple.PurpleStatusIsActive(status):
                        self.purple.PurpleStatusSetActive(status, False)
                else:
                    self.purple.PurpleStatusSetActive(status, True)
                    updated |= self.setStatus(status, "tune_title", title);
                    updated |= self.setStatus(status, "tune_artist", artist);
                    updated |= self.setStatus(status, "tune_album", album);
                if updated:
                    active = self.purple.PurplePresenceGetActiveStatus(p)
                    self.purple.PurplePrplChangeAccountStatus(account, active, status)

        return True

##############################################################################

def updateStatus() :
    """
        Information about the current track has changed
    """
    global mCurrentTrack
    global mCurrentTitle
    mCurrentTrack = APP.player.current

    title = unicode(getattr(mCurrentTrack, 'title'))
    if title == mCurrentTitle:
        return
    else :
        mCurrentTitle = title

    artist = unicode(getattr(mCurrentTrack, 'artist'))
    album = unicode(getattr(mCurrentTrack, 'album'))

    if APP.player.is_paused() :
        client.setTune("","","")
    else :
        client.setTune(artist, title, album)

def stop_track(exaile, track) :
    """
        Called when Exaile quits or when playback stops
    """
    # Stop event is sent also when a track is finished, even if Exaile is going to play the next one
    # Since we don't want to change the status between each track, we add a delay of 1/2 sec. before doing anything
    gobject.timeout_add(500, onStopTimer)


def onStopTimer() :
    """
        Called 1/2 sec. after the reception of a stop event
    """
    if not APP.player.is_playing() :
        client.setTune("","","")
    else :
        updateStatus()
    return False


def initialize(self = None):
    """
        Called when the plugin is enabled
    """

    global client
    obj = dbus.SessionBus().get_object('im.pidgin.purple.PurpleService',
                                   '/im/pidgin/purple/PurpleObject')
    purple = dbus.Interface(obj, "im.pidgin.purple.PurpleInterface")

    client = Pidgin(purple)

    # Add the handlers
    mHandlers.connect(APP.player, 'stop-track', stop_track)
    mHandlers. connect(APP.player, 'pause-toggled', lambda exaile, track : updateStatus())

    return True

def destroy() :
    """
        Called when the plugin is disabled
    """
    mHandlers.disconnect_all()
