# Copyright (C) 2014 Rocco Aliberti
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

try:
    import lxml.html
except ImportError:
    lxml = None

import re

from xl.lyrics import (
    LyricSearchMethod,
    LyricsNotFoundException
)
from xl import common, providers
from xl.common import str_from_utf8


def enable(exaile):
    """
        Enables the lyrics mania plugin that fetches track lyrics
        from lyricsmania.com
    """
    if lxml:
        providers.register('lyrics', LyricsMania(exaile))
    else:
        raise NotImplementedError('LXML is not available.')
        return False

def disable(exaile):
    providers.unregister('lyrics', providers.get_provider('lyrics',
        'lyricsmania'))

class LyricsMania(LyricSearchMethod):

    name= "lyricsmania"
    display_name = "Lyrics Mania"
    
    def __init__(self, exaile):
        self.user_agent = exaile.get_user_agent_string('lyricsmania')

    def find_lyrics(self, track):
        try:
            (artist, title) = str_from_utf8(track.get_tag_raw('artist')[0]), \
                str_from_utf8(track.get_tag_raw('title')[0])
        except TypeError:
            raise LyricsNotFoundException

        if not artist or not title:
            raise LyricsNotFoundException

        artist = artist.replace(' ','_').replace('\'','').lower()
        title = title.replace(' ','_').replace('\'','').lower()

        url = 'http://www.lyricsmania.com/%s_lyrics_%s.html' % (title, artist)

        try:
            html = common.get_url_contents(url, self.user_agent)
        except:
            raise LyricsNotFoundException

        try:
            lyrics_html = lxml.html.fromstring(html)
        except lxml.etree.XMLSyntaxError:
            raise LyricsNotFoundException

        try:
            lyrics_body = lyrics_html.find_class('lyrics-body')[0]
            lyrics_body.remove(lyrics_body.get_element_by_id('video-musictory'))
            lyrics = re.sub('^\s+Lyrics to .+', '', lyrics_body.text_content())
        except:
            raise LyricsNotFoundException

        # We end up with unicode in some systems, str (bytes) in others;
        # no idea why and which one is correct.
        if isinstance(lyrics, bytes):
            lyrics = common.to_unicode(lyrics, 'utf8', errors='replace')
        return (lyrics, self.name, url)
