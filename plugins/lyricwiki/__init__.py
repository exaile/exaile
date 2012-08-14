try:
    import BeautifulSoup
except ImportError:
    BeautifulSoup = None
import HTMLParser
import re
import urllib

from xl.lyrics import (
    LyricSearchMethod,
    LyricsNotFoundException
)
from xl import event

def enable(exaile):
    """
        Enables the lyric wiki plugin that fetches track lyrics
        from lyrics.wikia.com
    """
    if BeautifulSoup:
        if exaile.loading:
            event.add_callback(_enable, "exaile_loaded")
        else:
            _enable(None, exaile, None)
    else:
        raise NotImplementedError('BeautifulSoup is not available.')
        return False

def _enable(eventname, exaile, nothing):
    exaile.lyrics.add_search_method(LyricWiki())


def disable(exaile):
    exaile.lyrics.remove_search_method_by_name("lyricwiki")


class LyricWiki(LyricSearchMethod):

    name= "lyricwiki"
    display_name = "Lyric Wiki"

    def find_lyrics(self, track):
        try:
            (artist, title) = track.get_tag_raw('artist')[0].encode("utf-8"), \
                track.get_tag_raw('title')[0].encode("utf-8")
        except TypeError:
            raise LyricsNotFoundException

        if not artist or not title:
            raise LyricsNotFoundException

        artist = urllib.quote(artist.replace(' ','_'))
        title = urllib.quote(title.replace(' ','_'))

        url = 'http://lyrics.wikia.com/%s:%s' % (artist, title)

        try:
            html = urllib.urlopen(url).read()
        except:
            raise LyricsNotFoundException

        try:
            soup = BeautifulSoup.BeautifulSoup(html)
        except HTMLParser.HTMLParseError:
            raise LyricsNotFoundException
        lyrics = soup.findAll(attrs= {"class" : "lyricbox"})
        if lyrics:
            lyrics = re.sub(r' Send.*?Ringtone to your Cell ','','\n'.join(self.remove_html_tags(lyrics[0].renderContents().replace('<br />','\n')).replace('\n\n\n','').split('\n')[0:-7]))
        else:
            raise LyricsNotFoundException

        lyrics = str(BeautifulSoup.BeautifulStoneSoup(lyrics,convertEntities=BeautifulSoup.BeautifulStoneSoup.HTML_ENTITIES))

        return (lyrics, self.name, url)

    def remove_html_tags(self, data):
        p = re.compile(r'<[^<]*?/?>')
        data = p.sub('', data)
        p = re.compile(r'/<!--.*?-->/')
        return p.sub('',data)
