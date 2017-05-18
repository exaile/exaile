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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#

from contextlib import closing

from urllib import quote_plus
try:
    import xml.etree.cElementTree as ETree
except ImportError:
    import xml.etree.ElementTree as ETree

from xl import (
    common,
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
    LASTFM = LastFMCoverSearch(exaile)
    providers.register('covers', LASTFM)


def disable(exaile):
    providers.unregister('covers', LASTFM)


class LastFMCoverSearch(covers.CoverSearchMethod):
    """
        Searches Last.fm for covers
    """
    name = 'lastfm'
    title = 'Last.fm'
    type = 'remote'  # fetches remotely as opposed to locally

    url = 'https://ws.audioscrobbler.com/2.0/?method={type}.search&{type}={value}&api_key={api_key}'

    def __init__(self, exaile):
        self.user_agent = exaile.get_user_agent_string('lastfmcovers')

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

        for type, value in (('album', album), ('track', title)):
            url = self.url.format(
                type=type,
                value=quote_plus(value.encode("utf-8")),
                api_key=API_KEY
            )
            try:
                data = common.get_url_contents(url, self.user_agent)
            except IOError:
                continue

            try:
                xml = ETree.fromstring(data)
            except SyntaxError:
                continue

            for element in xml.getiterator(type):
                if (element.find('artist').text == artist.encode("utf-8")):
                    for sub_element in element.findall('image'):
                        if (sub_element.attrib['size'] == 'extralarge'):
                            url = sub_element.text
                            if url:
                                return [url]

        return []

    def get_cover_data(self, cover_url):
        try:
            return common.get_url_contents(cover_url, self.user_agent)
        except IOError:
            return None
