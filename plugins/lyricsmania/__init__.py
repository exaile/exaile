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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

try:
    import lxml.html
except ImportError:
    lxml = None

import re

from xl.lyrics import LyricSearchMethod, LyricsNotFoundException
from xl import common, providers


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
    providers.unregister('lyrics', providers.get_provider('lyrics', 'lyricsmania'))


class LyricsMania(LyricSearchMethod):

    name = "lyricsmania"
    display_name = "Lyrics Mania"

    def __init__(self, exaile):
        self.user_agent = exaile.get_user_agent_string('lyricsmania')

    def find_lyrics(self, track):
        try:
            (artist, title) = (
                track.get_tag_raw('artist')[0],
                track.get_tag_raw('title')[0],
            )
        except TypeError:
            raise LyricsNotFoundException

        if not artist or not title:
            raise LyricsNotFoundException

        artist = artist.replace(' ', '_').replace('\'', '').lower()
        title = title.replace(' ', '_').replace('\'', '').lower()

        url = 'https://www.lyricsmania.com/%s_lyrics_%s.html' % (title, artist)

        try:
            html = common.get_url_contents(url, self.user_agent)
        except Exception:
            raise LyricsNotFoundException

        try:
            lyrics_html = lxml.html.fromstring(html)
        except lxml.etree.XMLSyntaxError:
            raise LyricsNotFoundException

        try:
            lyrics_body = lyrics_html.find_class('lyrics-body')[0]
            lyrics_body.remove(lyrics_body.get_element_by_id('video-musictory'))
            lyrics = re.sub(r'^\s+Lyrics to .+', '', lyrics_body.text_content())
            lyrics = lyrics.replace('\t', '')
            lyrics = self.remove_script(lyrics)
            lyrics = self.remove_html_tags(lyrics)
        except Exception:
            raise LyricsNotFoundException

        # We end up with unicode in some systems, str (bytes) in others;
        # no idea why and which one is correct.
        if isinstance(lyrics, bytes):
            lyrics = lyrics.decode('utf-8', errors='replace')
        return (lyrics, self.name, url)
