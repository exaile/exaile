# Copyright (C) 2012 Dustin Spicuzza
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
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

import os

from xl.nls import gettext as _
from xlgui.preferences import playback

name = _('Preview Device')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, 'previewprefs.ui')
icon = 'media-playback-start'


def __autoconfig():
    """
    If the user hasn't used our plugin before, then try to
    autoconfig their audio settings to use a different audio
    device if possible..

    TODO: It would be cool if we could notify the user that
    a new device was plugged in...
    """

    from xl import settings

    if settings.get_option('preview_device/audiosink', None) is not None:
        return

    sink = settings.get_option('player/audiosink', None)
    if sink is None:
        return

    settings.set_option('preview_device/audiosink', sink)

    main_device = settings.get_option('player/audiosink_device', None)
    if main_device is None:
        return

    # TODO: If we ever add another engine, need to make sure that
    #       gstreamer-specific stuff doesn't accidentally get loaded
    from xl.player.gst.sink import get_devices

    # pick the first one that isn't the main device and isn't 'Auto'
    # -> if the main device is '', then it's auto. So... we actually
    # iterate backwards, assuming that the ordering matters
    for _unused, device_id, _unused in reversed(list(get_devices())):
        if device_id != main_device and name != 'auto':
            settings.set_option('preview_device/audiosink_device', device_id)
            break


__autoconfig()


class PreviewDeviceEnginePreference(playback.EnginePreference):
    name = 'preview_device/engine'


class PreviewDeviceAudioSinkPreference(playback.AudioSinkPreference):
    name = 'preview_device/audiosink'


class PreviewDeviceCustomAudioSinkPreference(playback.CustomAudioSinkPreference):
    name = 'preview_device/custom_sink_pipe'
    condition_preference_name = 'preview_device/audiosink'


class PreviewDeviceSelectDeviceForSinkPreference(
    playback.SelectDeviceForSinkPreference
):
    name = 'preview_device/audiosink_device'
    condition_preference_name = 'preview_device/audiosink'


class PreviewDeviceUserFadeTogglePreference(playback.UserFadeTogglePreference):
    name = 'preview_device/user_fade_enabled'
    condition_preference_name = 'preview_device/engine'


class PreviewDeviceUserFadeDurationPreference(playback.UserFadeDurationPreference):
    name = 'preview_device/user_fade'
    condition_preference_name = 'preview_device/engine'


class PreviewDeviceCrossFadingPreference(playback.CrossfadingPreference):
    default = False
    name = 'preview_device/crossfading'
    condition_preference_name = 'preview_device/engine'


class PreviewDeviceCrossfadeDurationPreference(playback.CrossfadeDurationPreference):
    default = 1000
    name = 'preview_device/crossfade_duration'
    condition_preference_name = 'preview_device/engine'
