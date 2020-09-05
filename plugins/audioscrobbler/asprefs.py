# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

from gi.repository import GLib
from gi.repository import Gtk

import os.path
from . import _scrobbler

from xl import common, settings
from xl.nls import gettext as _
from xlgui import icons
from xlgui.preferences import widgets
from xlgui.widgets import dialogs

name = _('AudioScrobbler')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "asprefs_pane.ui")

icons.MANAGER.add_icon_name_from_directory(
    'audioscrobbler', os.path.join(basedir, 'icons')
)
icon = 'audioscrobbler'


class SubmitPreference(widgets.CheckPreference):
    default = True
    name = 'plugin/ascrobbler/submit'


class MenuCheck(widgets.CheckPreference):
    default = False
    name = 'plugin/ascrobbler/menu_check'


class ScrobbleRemote(widgets.CheckPreference):
    default = False
    name = 'plugin/ascrobbler/scrobble_remote'


class UserPreference(widgets.Preference):
    name = 'plugin/ascrobbler/user'


class PassPreference(widgets.HashedPreference):
    name = 'plugin/ascrobbler/password'


class UrlPreference(widgets.ComboEntryPreference):
    name = 'plugin/ascrobbler/url'
    default = 'http://post.audioscrobbler.com/'
    preset_items = {
        'http://post.audioscrobbler.com/': 'Last.fm',
        'http://turtle.libre.fm/': 'Libre.fm',
    }


class VerifyLoginButton(widgets.Button):
    name = 'plugin/ascrobbler/verify_login'

    def __init__(self, preferences, widget):
        """
        Sets up the message
        """
        widgets.Button.__init__(self, preferences, widget)

        self.message = dialogs.MessageBar(
            parent=preferences.builder.get_object('preferences_box'),
            buttons=Gtk.ButtonsType.CLOSE,
        )

    @common.threaded
    def check_login(self):
        """
        Tries to connect to the AudioScrobbler
        service with the existing login data
        """
        username = settings.get_option('plugin/ascrobbler/user', '')
        password = settings.get_option('plugin/ascrobbler/password', '')
        url = settings.get_option(
            'plugin/ascrobbler/url', 'http://post.audioscrobbler.com/'
        )
        login_verified = False

        try:
            _scrobbler.login(username, password, post_url=url)
        except _scrobbler.AuthError:
            try:
                _scrobbler.login(username, password, hashpw=True, post_url=url)
            except _scrobbler.AuthError:
                pass
            else:
                login_verified = True
        else:
            login_verified = True

        if login_verified:
            GLib.idle_add(self.message.show_info, _('Verification successful'), '')
        else:
            GLib.idle_add(
                self.message.show_error,
                _('Verification failed'),
                _('Please make sure the entered data is correct.'),
            )

        GLib.idle_add(self.widget.set_sensitive, True)

    def on_clicked(self, button):
        """
        Initiates verification of the login data
        """
        self.widget.set_sensitive(False)
        self.check_login()
