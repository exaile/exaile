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

import subprocess
import logging
import os
import shutil
from gi.repository import Gtk

from xl import event, player, settings
from xl.nls import gettext as _
from xlgui.widgets import dialogs

from . import srprefs

logger = logging.getLogger(__name__)

STREAMRIPPER = None


def get_preferences_pane():
    return srprefs


class Streamripper:
    def __init__(self):
        self.savedir = None

    def toggle_record(self, add_call):
        current_track = player.PLAYER.current
        if not current_track:
            return True
        if current_track.is_local():
            logger.warning('Streamripper can only record streams')
            return True

        self.savedir = settings.get_option(
            'plugin/streamripper/save_location', os.getenv('HOME')
        )
        options = []
        options.append('streamripper')
        options.append(player.PLAYER._pipe.get_property('uri'))
        options.append('-D')
        options.append('%A/%a/%T')
        if settings.get_option('plugin/streamripper/single_file', False):
            options.append("-a")
            options.append("-A")
        options.append("-r")
        options.append(settings.get_option('plugin/streamripper/relay_port', '8888'))
        options.append("-d")
        options.append(self.savedir)

        try:
            self.process = subprocess.Popen(
                options, 0, None, subprocess.PIPE, subprocess.PIPE, subprocess.PIPE
            )
        except OSError:
            logger.error('There was an error executing streamripper')
            dialogs.error(
                self.exaile.gui.main.window, _('Error ' 'executing streamripper')
            )
            return True

        if add_call:
            event.add_callback(self.quit_application, 'quit_application')
            event.add_ui_callback(
                self.start_track, 'playback_track_start', player.PLAYER
            )
            event.add_ui_callback(
                self.stop_playback, 'playback_player_end', player.PLAYER
            )
        return False

    def stop_ripping(self):
        try:
            self.process.terminate()
        except Exception:
            pass
        if settings.get_option('plugin/streamripper/delete_incomplete', True):
            try:
                shutil.rmtree(self.savedir + "/incomplete")
            except OSError:
                pass

    def quit_application(self, type, player, track):
        self.stop_ripping()

    def stop_playback(self, type, player, track):
        self.stop_ripping()
        self.button.set_active(False)
        self.remove_callbacks()

    def start_track(self, type, player, track):
        self.stop_ripping()
        if self.toggle_record(False):
            self.button.set_active(False)
            self.remove_callbacks()

    def remove_callbacks(self):
        event.remove_callback(self.quit_application, 'quit_application')
        event.remove_callback(self.start_track, 'playback_track_start', player.PLAYER)
        event.remove_callback(self.stop_playback, 'playback_player_end', player.PLAYER)


class Button(Streamripper):
    def __init__(self, exaile):
        self.exaile = exaile
        self.button = Gtk.ToggleButton()
        self.button.set_relief(Gtk.ReliefStyle.NONE)
        image = Gtk.Image.new_from_icon_name('media-record', Gtk.IconSize.MENU)
        self.button.set_image(image)

        toolbar = self.exaile.gui.play_toolbar
        toolbar.pack_start(self.button, False, False, 0)
        toolbar.reorder_child(self.button, 3)

        self.button.show()

        self.button.connect('button-release-event', self.toggle_button_callback)

    def toggle_button_callback(self, widget, data):
        if widget.get_active():
            self.stop_ripping()
            self.remove_callbacks()
        else:
            if self.toggle_record(True):  # couldn't record stream
                self.button.set_active(True)
                self.remove_callbacks()

    def remove_button(self):
        self.exaile.gui.play_toolbar.remove(self.button)
        self.button.hide()
        self.button.destroy()
        self.remove_callbacks()


def enable(exaile):
    try:  # just test if streamripper is installed
        subprocess.call(['streamripper'], stdout=-1, stderr=-1)
    except OSError:
        raise NotImplementedError('Streamripper is not available.')
        return False

    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)


def _enable(eventname, exaile, nothing):
    global STREAMRIPPER
    STREAMRIPPER = Button(exaile)


def disable(exaile):
    global STREAMRIPPER
    STREAMRIPPER.remove_button()
    STREAMRIPPER = None
