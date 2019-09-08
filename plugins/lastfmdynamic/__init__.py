# Copyright (C) 2009-2010 Aren Olson
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

import xml.etree.ElementTree as ETree
import urllib.parse
import urllib.request
from xl.dynamic import DynamicSource
from xl import providers

import logging

logger = logging.getLogger(__name__)

LFMS = None

# Last.fm API Key for Exaile
# if you reuse this code in a different application, please
# register your own key with last.fm
API_KEY = '3599c79a97fd61ce518b75922688bc38'


def enable(exaile):
    global LFMS
    LFMS = LastfmSource()
    providers.register("dynamic_playlists", LFMS)


def disable(exaile):
    global LFMS
    providers.unregister("dynamic_playlists", LFMS)
    LFMS = None


class LastfmSource(DynamicSource):
    name = 'lastfm'

    def __init__(self):
        DynamicSource.__init__(self)

    def get_results(self, artist):
        ar = urllib.parse.quote_plus(artist.encode('utf-8'))
        url = (
            'https://ws.audioscrobbler.com/2.0/?method=artist.getsimilar&artist=%s&api_key='
            + API_KEY
        )
        try:
            f = urllib.request.urlopen(url % ar).read()
        except IOError:
            logger.exception("Error retrieving results")
            return []

        retlist = []
        xml = ETree.fromstring(f)

        for e in xml.getiterator('artist'):
            retlist.append((float(e.find('match').text), e.find('name').text))

        return retlist
