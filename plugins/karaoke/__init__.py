# karaoke - Removes voice from Exaile's audio output
# Copyright (C) 2009-2010  Johannes Sasongko <sasongko@gmail.com>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import gst
import xl.providers
from xl.player.pipe import ElementBin


class Karaoke(ElementBin):
    index = 50
    name = 'karaoke'
    def __init__(self, player):
        ElementBin.__init__(self, player, name=self.name)
        self.elements[50] = gst.element_factory_make('audiokaraoke')
        self.setup_elements()


def enable(exaile):
    xl.providers.register('stream_element', Karaoke)

def disable(exaile):
    xl.providers.unregister('stream_element', Karaoke)


# vi: et sts=4 sw=4 tw=80
