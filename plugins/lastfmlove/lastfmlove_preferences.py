# Copyright (C) 2011 Mathias Brodala
#
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

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

import os.path

import pylast

from xl.nls import gettext as _
from xl import common, settings
from xlgui import icons
from xlgui.preferences import widgets
from xlgui.widgets import dialogs

name = _('Last.fm Loved Tracks')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "lastfmlove_preferences.ui")
icons.MANAGER.add_icon_name_from_directory('lastfm', os.path.join(basedir, 'icons'))
icon = 'lastfm'


class APIKeyPreference(widgets.Preference):
    name = 'plugin/lastfmlove/api_key'


class APISecretPrefence(widgets.Preference):
    name = 'plugin/lastfmlove/api_secret'


class RequestAccessPermissionButton(widgets.Button):
    name = 'plugin/lastfmlove/request_access_permission'

    def __init__(self, preferences, widget):
        """
        Sets up the message
        """
        widgets.Button.__init__(self, preferences, widget)

        self.message = dialogs.MessageBar(
            parent=preferences.builder.get_object('preferences_box'),
            buttons=Gtk.ButtonsType.CLOSE,
        )
        self.errors = {pylast.STATUS_INVALID_API_KEY: _('The API key is invalid.')}

    @common.threaded
    def check_connection(self):
        """
        Checks API key and secret for validity
        and opens the URI for access permission
        """
        api_key = settings.get_option('plugin/lastfmlove/api_key', 'K')

        try:
            pylast.LastFMNetwork(
                api_key=api_key,
                api_secret=settings.get_option('plugin/lastfmlove/api_secret', 'S'),
                username=settings.get_option('plugin/ascrobbler/user', ''),
                password_hash=settings.get_option('plugin/ascrobbler/password', ''),
            )
        except pylast.WSError as e:
            GLib.idle_add(
                self.message.show_error,
                self.errors[int(e.get_id())],
                _('Please make sure the entered data is correct.'),
            )
        else:
            application_launched = Gtk.show_uri(
                Gdk.Screen.get_default(),
                'http://www.last.fm/api/auth?api_key={0}'.format(api_key),
                Gdk.CURRENT_TIME,
            )

            if not application_launched:
                url = 'http://www.last.fm/api/auth?api_key={0}'.format(api_key)
                GLib.idle_add(
                    self.message.show_warning,
                    _('Could not start web browser'),
                    _(
                        'Please copy the following URL and '
                        'open it with your web browser:\n'
                        '<b><a href="{url}">{url}</a></b>'
                    ).format(url=url),
                )

    def on_clicked(self, button):
        """
        Initiates the check for validity
        """
        self.check_connection()
