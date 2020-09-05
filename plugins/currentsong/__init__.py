# -*- coding: utf-8 -*-

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

# Code based on Ingelrest FranÃ§ois' "im status" plugin

import dbus
from xl import event, player

##############################################################################


class Pidgin:
    def __init__(self, dbusInterface):
        """
        Constructor
        """
        self.purple = dbusInterface

    def listAccounts(self):
        """
        Purple merges all accounts, so we return a default one
        Each account is associated with:
            * A boolean -> True if the status of this account was changed on the previous track change
        """
        return {'GenericAccount': False}

    def setStatus(self, status, attr, value):
        # this doesn't actually work, for some reason the getter always return ""
        if self.purple.PurpleStatusGetAttrString(status, attr) != value:
            self.purple.PurpleStatusSetAttrString(status, attr, value)
            return True
        return False

    def setTune(self, artist, title, album):
        """
        Change the tune status
        Return True if the message is successfully updated
        """
        accounts = self.purple.PurpleAccountsGetAll()

        for account in accounts:
            if not self.purple.PurpleAccountIsConnected(account):
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
                    updated |= self.setStatus(status, "tune_title", title)
                    updated |= self.setStatus(status, "tune_artist", artist)
                    updated |= self.setStatus(status, "tune_album", album)
                if updated:
                    active = self.purple.PurplePresenceGetActiveStatus(p)
                    self.purple.PurplePrplChangeAccountStatus(account, active, status)

        return True


##############################################################################


def on_begin_action(type, player, track):
    client.setTune(
        track.get_tag_display('artist'),
        track.get_tag_display('title'),
        track.get_tag_display('album'),
    )


def on_stop_action(type, player, track):
    client.setTune("", "", "")


def on_pause_action(type, player, track):
    if player.is_playing():
        on_begin_action(type, player, track)
    else:
        on_stop_action(type, player, track)


def enable(exaile):
    global client
    obj = dbus.SessionBus().get_object(
        'im.pidgin.purple.PurpleService', '/im/pidgin/purple/PurpleObject'
    )
    purple = dbus.Interface(obj, "im.pidgin.purple.PurpleInterface")
    client = Pidgin(purple)
    event.add_callback(on_stop_action, 'quit_application')
    event.add_callback(on_stop_action, 'playback_player_end', player.PLAYER)
    event.add_callback(on_begin_action, 'playback_track_start', player.PLAYER)
    event.add_callback(on_pause_action, 'playback_toggle_pause', player.PLAYER)


def disable(exaile):
    event.remove_callback(on_stop_action, 'quit_application')
    event.remove_callback(on_stop_action, 'playback_player_end', player.PLAYER)
    event.remove_callback(on_begin_action, 'playback_track_start', player.PLAYER)
    event.remove_callback(on_pause_action, 'playback_toggle_pause', player.PLAYER)
