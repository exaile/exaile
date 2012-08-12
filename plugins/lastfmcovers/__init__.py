# Copyright (C) 2009-2010 Aren Olson, Johannes Schwarz
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import hashlib
import urllib
try:
    import xml.etree.cElementTree as ETree
except:
    import xml.etree.ElementTree as ETree

from xl import (
    covers,
    event,
    providers
)

# Last.fm API Key for Exaile
# if you reuse this code in a different application, please
# register your own key with last.fm
API_KEY = '3599c79a97fd61ce518b75922688bc38'

LASTFM = None

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, "exaile_loaded")
    else:
        _enable(None, exaile, None)

def _enable(eventname, exaile, nothing):
    global LASTFM
    LASTFM = LastFMCoverSearch()
    providers.register('covers', LASTFM)

def disable(exaile):
    providers.unregister('covers', LASTFM)


class LastFMCoverSearch(covers.CoverSearchMethod):
    """
        Searches Last.fm for covers
    """
    name = 'lastfm'
    title = 'Last.fm'
    type = 'remote' # fetches remotely as opposed to locally

    url = 'http://ws.audioscrobbler.com/2.0/?method=type.search&type=%(type)s&api_key='


    def find_covers(self, track, limit=-1):
        """
            Searches last.fm for album covers
        """
        # TODO: handle multi-valued fields better
        try:
            (artist, album, title) = track.get_tag_raw('artist')[0], \
                track.get_tag_raw('album')[0], \
                track.get_tag_raw('title')[0]
        except TypeError:
            return []

        if not artist or not album or not title:
            return []

        for type in [['album', album], ['track', title]]:
            url_exact = self.url.replace('type', type[0]) + API_KEY
            try:
                data = urllib.urlopen(url_exact %
                {
                    type[0]: urllib.quote_plus(type[1].encode("utf-8"))
                }).read()
            except IOError:
                continue

            xml = ETree.fromstring(data)

            for element in xml.getiterator(type[0]):
                if (element.find('artist').text == artist.encode("utf-8")):
                    for sub_element in element.findall('image'):
                        if (sub_element.attrib['size'] == 'extralarge'):
                            url = sub_element.text
                            if url:
                                return [url]

        return []

    def get_cover_data(self, cover_url):
        try:
            h = urllib.urlopen(cover_url)
            data = h.read()
            h.close()
        except IOError:
            return None
        return data

