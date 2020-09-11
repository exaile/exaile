try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
import re
import urllib.parse

from xl.lyrics import LyricSearchMethod, LyricsNotFoundException
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

    name = "lyricwiki"
    display_name = "Lyric Wiki"

    def __init__(self, exaile):
        self.user_agent = exaile.get_user_agent_string('lyricwiki')

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

        artist = urllib.parse.quote(artist.replace(' ', '_'))
        title = urllib.parse.quote(title.replace(' ', '_'))

        url = 'https://lyrics.fandom.com/wiki/%s:%s' % (artist, title)

        try:
            source = common.get_url_contents(url, self.user_agent)
        except Exception:
            raise LyricsNotFoundException

        soup = BeautifulSoup(source, "lxml")
        lyrics = soup.findAll(attrs={"class": "lyricbox"})
        if lyrics:
            with_div = (
                lyrics[0].renderContents().decode('utf-8').replace('<br />', '\n')
            )
            string = '\n'.join(
                self.remove_div(with_div).replace('\n\n\n', '').split('\n')
            )
            lyrics = re.sub(r' Send.*?Ringtone to your Cell ', '', string)
        else:
            raise LyricsNotFoundException

        lyrics = self.remove_script(lyrics)
        lyrics = self.remove_html_tags(str(BeautifulSoup(lyrics, "lxml")))

        return (lyrics, self.name, url)
