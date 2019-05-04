# mono - Downmix Exaile's audio to one channel
# Copyright (C) 2013  Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
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


from gi.repository import Gst

import xl.providers
from xl.player.gst.gst_utils import ElementBin


class Mono(ElementBin):
    index = 90
    name = 'mono'

    def __init__(self):
        ElementBin.__init__(self, name=self.name)
        # self.elements[50] = Gst.ElementFactory.make('audioconvert', None)
        self.elements[60] = cf = Gst.ElementFactory.make('capsfilter', None)
        cf.props.caps = Gst.Caps.from_string('audio/x-raw,channels=1')
        self.setup_elements()


def enable(exaile):
    xl.providers.register('gst_audio_filter', Mono)


def disable(exaile):
    xl.providers.unregister('gst_audio_filter', Mono)


# vi: et sts=4 sw=4 tw=80
