# Copyright (C) 2009 Aren Olson, Johannes Schwarz
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

try:
    import xml.etree.cElementTree as ETree
except:
    import xml.etree.ElementTree as ETree
import hashlib, urllib
from xl.cover import *
from xl import event

# Last.fm API Key for Exaile
# if you reuse this code in a different application, please
# register your own key with last.fm
API_KEY = '3599c79a97fd61ce518b75922688bc38'


def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, "exaile_loaded")
    else:
        _enable(None, exaile, None)

def _enable(eventname, exaile, nothing):
    exaile.covers.add_search_method(LastFMCoverSearch())

def disable(exaile):
    exaile.covers.remove_search_method_by_name('lastfm')


class LastFMCoverSearch(CoverSearchMethod):
    """
        Searches Last.fm for covers
    """
    name = 'lastfm'
    type = 'remote' # fetches remotely as opposed to locally

    url = 'http://ws.audioscrobbler.com/2.0/?method=type.search&type=%(type)s&api_key='


    def find_covers(self, track, limit=-1):
        """
            Searches last.fm for album covers
        """

        # TODO: handle multi-valued fields better
        (artist, album, title) = track.get_tag_raw('artist')[0], \
                track.get_tag_raw('album')[0], \
                track.get_tag_raw('title')[0]

        if not artist or not album or not title:
            raise NoCoverFoundException()

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
                            return [self.save_cover(sub_element.text)]

        raise NoCoverFoundException()

    def save_cover(self, cover_url):

        h = urllib.urlopen(cover_url)
        data = h.read()
        h.close()

        cache_dir = self.manager.cache_dir

        covername = os.path.join(cache_dir, hashlib.md5(cover_url).hexdigest())
        covername += ".jpg"
        h = open(covername, 'wb')
        h.write(data)
        h.close()

        return covername

