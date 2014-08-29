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
from xl import common, providers

def enable(exaile):
    """
        Enables the lyric wiki plugin that fetches track lyrics
        from lyrics.wikia.com
    """
    if BeautifulSoup:
        providers.register('lyrics', LyricWiki(exaile))
    else:
        raise NotImplementedError('BeautifulSoup is not available.')
        return False

def disable(exaile):
    providers.unregister('lyrics', providers.get_provider('lyrics', 'lyricwiki'))

class LyricWiki(LyricSearchMethod):

    name= "lyricwiki"
    display_name = "Lyric Wiki"
    
    def __init__(self, exaile):
        self.user_agent = exaile.get_user_agent_string('lyricwiki')

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
            html = common.get_url_contents(url, self.user_agent)
        except:
            raise LyricsNotFoundException

        try:
            soup = BeautifulSoup.BeautifulSoup(html)
        except HTMLParser.HTMLParseError:
            raise LyricsNotFoundException
        lyrics = soup.findAll(attrs= {"class" : "lyricbox"})
        if lyrics:
            lyrics = re.sub(r' Send.*?Ringtone to your Cell ','','\n'.join(self.remove_div(lyrics[0].renderContents().replace('<br />','\n')).replace('\n\n\n','').split('\n')[0:-7]))
        else:
            raise LyricsNotFoundException

        lyrics = self.remove_script(lyrics)
        lyrics = self.remove_html_tags(str(BeautifulSoup.BeautifulStoneSoup(lyrics,convertEntities=BeautifulSoup.BeautifulStoneSoup.HTML_ENTITIES)))

        return (lyrics, self.name, url)

    def remove_script(self, data):
        p = re.compile(r'<script.*/script>')
        return p.sub('',data)

    def remove_div(self,data):
        p = re.compile(r'<div.*/div>')
        return p.sub('',data)
            
    def remove_html_tags(self, data):
        p = re.compile(r'<[^<]*?/?>')
        data = p.sub('', data)
        p = re.compile(r'/<!--.*?-->/')
        return p.sub('',data)
